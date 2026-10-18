import os
import time
import statistics
from pathlib import Path

from findex5.index import build_distributed_index_with_metrics

DATA_DIR = Path(r"D:\pr\findex1\data")
RUNS = 3


def run_benchmark_table_only():
    if not DATA_DIR.exists():
        print(f"❌ Шлях до даних не знайдено: {DATA_DIR}")
        return

    all_paths = sorted(list(DATA_DIR.rglob("*.txt")))
    if not all_paths:
        print("❌ Не знайдено текстових файлів для бенчмарку.")
        return

    cpu_count = os.cpu_count() or 4
    workers_list = sorted(list(set([1, 2, 4, 8, cpu_count])))
    executors = ["serial", "threads", "processes"]

    results = []
    baseline_wall = None

    print(f"🚀 Запуск бенчмарку для {len(all_paths)} файлів (CPU cores: {cpu_count})...\n")

    for executor in executors:
        for workers in workers_list:
            if executor == "serial" and workers > 1:
                continue

            wall_times = []
            cpu_times = []
            merge_times = []

            for run in range(RUNS):
                start_cpu = time.process_time()
                start_wall = time.perf_counter()

                _, merge_t = build_distributed_index_with_metrics(
                    all_paths=all_paths,
                    workers=workers,
                    executor_type=executor,
                    with_positions=False
                )

                end_wall = time.perf_counter()
                end_cpu = time.process_time()

                wall_time = end_wall - start_wall
                cpu_time = end_cpu - start_cpu

                wall_times.append(wall_time)
                cpu_times.append(cpu_time)
                merge_times.append(merge_t)

            median_wall = statistics.median(wall_times)
            median_cpu = statistics.median(cpu_times)
            median_merge = statistics.median(merge_times)

            if executor == "serial" and workers == 1:
                baseline_wall = median_wall

            speedup = baseline_wall / median_wall if baseline_wall else 1.0

            results.append({
                "executor": executor,
                "workers": workers,
                "wall": median_wall,
                "cpu": median_cpu,
                "rss": 0.0,  # Заглушка без psutil
                "merge": median_merge,
                "speedup": speedup,
            })
            print(f"[{executor.upper():9} | W:{workers}] -> Wall: {median_wall:.2f}s | Speedup: {speedup:.2f}x")


    print("\n" + "=" * 85)
    print(
        f"{'Executor':<10} | {'Workers':<7} | {'Wall (s)':<10} | {'CPU (s)':<10} | {'Peak RSS':<10} | {'Merge (s)':<10} | {'Speedup':<8}")
    print("-" * 85)
    for r in results:
        rss_str = "N/A" if r['rss'] == 0.0 else f"{r['rss']:.1f}M"
        print(
            f"{r['executor']:<10} | {r['workers']:<7} | {r['wall']:<10.2f} | {r['cpu']:<10.2f} | {rss_str:<10} | {r['merge']:<10.2f} | {r['speedup']:<7.2f}×")
    print("=" * 85)


if __name__ == "__main__":
    run_benchmark_table_only()