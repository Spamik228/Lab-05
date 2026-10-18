from pathlib import Path
from findex5.index import build_partial, merge, build_index
from findex5.tokenizer import tokenize

DATA_DIR = Path(r"D:\pr\findex1\data")

def load_arxiv_corpus(data_dir: Path, max_docs: int = 1000):
    print(f"📂 Зчитування файлів з {data_dir}...")
    corpus = []
    doc_texts = {}

    txt_files = sorted(list(data_dir.glob("*.txt")))[:max_docs]
    if not txt_files:
        print(f"❌ Файлів .txt не знайдено за шляхом: {data_dir}")
        return [], {}

    # Змінюємо start=0 для сумісності з нумерацією у частинах
    for doc_id, file_path in enumerate(txt_files, start=0):
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        title = lines[0] if lines else file_path.stem

        corpus.append(
            {
                "doc_id": doc_id,
                "title": title,
                "path": str(file_path),
                "tokens": list(tokenize(content)),
            }
        )
        doc_texts[doc_id] = content

    print(f"✅ Успішно зчитано {len(corpus)} документів.")
    return corpus, doc_texts


def test_milestone1_with_arxiv_corpus():
    if not DATA_DIR.exists():
        return

    # 1. Отримуємо стандартний корпус через твою функцію
    corpus, _ = load_arxiv_corpus(DATA_DIR, max_docs=1000)
    assert len(corpus) > 0

    # 2. Витягуємо шляхи з отриманого корпусу для build_partial
    all_paths = [Path(doc["path"]) for doc in corpus]

    # 3. Новий підхід через частковий індекс і злиття
    partial = build_partial(all_paths, with_positions=False)
    index_merged = merge([partial])

    # 4. Класичний підхід через build_index
    index_standard = build_index(corpus, with_positions=False)

    # 5. Перевіряємо, що результати ідентичні
    assert index_merged.num_docs == index_standard.num_docs
    assert len(index_merged) == len(index_standard)
    assert index_merged.avg_doc_length == index_standard.avg_doc_length

    for term in index_merged:
        assert term in index_standard
        assert index_merged[term] == index_standard[term]