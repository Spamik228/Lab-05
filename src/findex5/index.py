from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import NotRequired, TypedDict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from findex5.tokenizer import tokenize
from findex5.utils import timed
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

class CorpusDocument(TypedDict):
    doc_id: int
    tokens: list[str]
    path: NotRequired[str]
    title: NotRequired[str]


@dataclass(frozen=True, slots=True)
class DocMeta:
    doc_id: int
    path: str
    title: str


@dataclass(frozen=True, slots=True)
class Posting:
    doc_id: int
    tf: int
    positions: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PartialIndex:
    postings: dict[str, list[Posting]]
    doc_lengths: dict[int, int]
    doc_meta: dict[int, DocMeta]


class Index(Mapping[str, list[Posting]]):
    def __init__(
        self,
        postings: dict[str, list[Posting]],
        doc_lengths: dict[int, int],
        doc_meta: dict[int, DocMeta],
    ) -> None:
        self._postings = postings
        self._doc_lengths = doc_lengths
        self._doc_meta = doc_meta

    def __len__(self) -> int:
        return len(self._postings)

    def __contains__(self, term: object) -> bool:
        return term in self._postings

    def __getitem__(self, term: str) -> list[Posting]:
        return self._postings[term]

    def __iter__(self) -> Iterator[str]:
        return iter(self._postings)

    def __repr__(self) -> str:
        return (
            f"Index(terms={len(self)}, "
            f"num_docs={self.num_docs}, "
            f"avg_doc_length={self.avg_doc_length:.2f})"
        )

    @property
    def num_docs(self) -> int:
        return len(self._doc_meta)

    @cached_property
    def avg_doc_length(self) -> float:
        if not self._doc_lengths:
            return 0.0
        return sum(self._doc_lengths.values()) / len(self._doc_lengths)

    def doc_length(self, doc_id: int) -> int:
        return self._doc_lengths.get(doc_id, 0)

    def df(self, term: str) -> int:
        if term in self._postings:
            return len(self._postings[term])
        return 0


def build_partial(
    doc_paths: list[Path],
    with_positions: bool = False,
) -> PartialIndex:

    postings: dict[str, list[Posting]] = defaultdict(list)
    doc_lengths: dict[int, int] = {}
    doc_meta: dict[int, DocMeta] = {}

    for local_doc_id, file_path in enumerate(doc_paths):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            tokens = list(tokenize(text))
            path_str = str(file_path.resolve())
            title = file_path.stem

            doc_meta[local_doc_id] = DocMeta(
                doc_id=local_doc_id,
                path=path_str,
                title=title,
            )
            doc_lengths[local_doc_id] = len(tokens)

            if with_positions:
                term_positions: dict[str, list[int]] = defaultdict(list)
                for pos, token in enumerate(tokens):
                    term_positions[token].append(pos)

                for term, positions in term_positions.items():
                    postings[term].append(
                        Posting(
                            doc_id=local_doc_id,
                            tf=len(positions),
                            positions=tuple(positions),
                        )
                    )
            else:
                counts = Counter(tokens)
                for term, tf in counts.items():
                    postings[term].append(Posting(doc_id=local_doc_id, tf=tf))
        except Exception as e:
            continue

    return PartialIndex(
        postings=dict(postings),
        doc_lengths=doc_lengths,
        doc_meta=doc_meta,
    )


def merge(partials: Iterable[PartialIndex]) -> Index:

    merged_postings: dict[str, list[Posting]] = defaultdict(list)
    merged_doc_lengths: dict[int, int] = {}
    merged_doc_meta: dict[int, DocMeta] = {}

    current_doc_offset = 0

    for partial in partials:
        id_map: dict[int, int] = {}
        for local_id in partial.doc_meta.keys():
            global_id = current_doc_offset + local_id
            id_map[local_id] = global_id

        for local_id, length in partial.doc_lengths.items():
            global_id = id_map[local_id]
            merged_doc_lengths[global_id] = length

        for local_id, meta in partial.doc_meta.items():
            global_id = id_map[local_id]
            merged_doc_meta[global_id] = DocMeta(
                doc_id=global_id,
                path=meta.path,
                title=meta.title,
            )

        for term, plist in partial.postings.items():
            new_plist = [
                Posting(
                    doc_id=id_map[p.doc_id],
                    tf=p.tf,
                    positions=p.positions,
                )
                for p in plist
            ]
            merged_postings[term].extend(new_plist)

        current_doc_offset += len(partial.doc_meta)

    for term in merged_postings:
        merged_postings[term].sort(key=lambda p: p.doc_id)

    return Index(
        postings=dict(merged_postings),
        doc_lengths=merged_doc_lengths,
        doc_meta=merged_doc_meta,
    )


def _build_partial_wrapper(args: tuple[list[Path], bool]) -> PartialIndex:
    doc_paths, with_positions = args
    return build_partial(doc_paths, with_positions=with_positions)


def build_distributed_index_with_metrics(
        all_paths: list[Path],
        workers: int = 4,
        executor_type: str = "serial",
        with_positions: bool = False,
) -> tuple[Index, float]:

    if not all_paths:
        return merge([]), 0.0

    n_chunks = max(1, min(workers, len(all_paths)))
    chunk_size = len(all_paths) // n_chunks

    chunks = []
    for i in range(n_chunks):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < n_chunks - 1 else len(all_paths)
        chunks.append(all_paths[start:end])

    task_args = [(chunk, with_positions) for chunk in chunks]
    partials = []


    if executor_type == "serial":
        for arg in task_args:
            partials.append(_build_partial_wrapper(arg))
    elif executor_type == "threads":
        with ThreadPoolExecutor(max_workers=workers) as executor:
            partials = list(executor.map(_build_partial_wrapper, task_args))
    elif executor_type == "processes":
        with ProcessPoolExecutor(max_workers=workers) as executor:
            partials = list(executor.map(_build_partial_wrapper, task_args))
    else:
        raise ValueError(f"Невідомий екзекутор: {executor_type}")

    # Фаза злиття (merge) із заміром часу
    merge_start = time.perf_counter()
    index = merge(partials)
    merge_time = time.perf_counter() - merge_start

    return index, merge_time

@timed
def build_index(
    corpus: Iterable[CorpusDocument],
    with_positions: bool = False,
) -> Index:

    postings: dict[str, list[Posting]] = defaultdict(list)
    doc_lengths: dict[int, int] = {}
    doc_meta: dict[int, DocMeta] = {}

    for doc in corpus:
        doc_id: int = doc["doc_id"]
        tokens: list[str] = doc["tokens"]

        doc_meta[doc_id] = DocMeta(
            doc_id=doc_id,
            path=doc.get("path", ""),
            title=doc.get("title", ""),
        )
        doc_lengths[doc_id] = len(tokens)

        if with_positions:
            term_positions: dict[str, list[int]] = defaultdict(list)
            for pos, token in enumerate(tokens):
                term_positions[token].append(pos)

            for term, positions in term_positions.items():
                postings[term].append(
                    Posting(
                        doc_id=doc_id,
                        tf=len(positions),
                        positions=tuple(positions),
                    )
                )
        else:
            counts = Counter(tokens)
            for term, tf in counts.items():
                postings[term].append(Posting(doc_id=doc_id, tf=tf))

    return Index(
        postings=dict(postings),
        doc_lengths=doc_lengths,
        doc_meta=doc_meta,
    )