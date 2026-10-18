import os
import time
import statistics
from pathlib import Path
import psutil
import matplotlib.pyplot as plt

from findex5.index import build_distributed_index_with_metrics

DATA_DIR = Path(r"D:\pr\findex1\data")
RUNS = 3


def run_benchmark():
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

    process = psutil.Process(os.getpid())

    for executor in executors:
        for workers in workers_list:

            if executor == "serial" and workers > 1:
                continue

            wall_times = []
            cpu_times = []
            rss_peaks = []
            merge_times = []

            for run in range(RUNS):
                # Очистка пам'яті перед прогоном
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
                peak_rss = process.memory_info().rss / (1024 * 1024)  # в MB

                wall_times.append(wall_time)
                cpu_times.append(cpu_time)
                rss_peaks.append(peak_rss)
                merge_times.append(merge_t)

            median_wall = statistics.median(wall_times)
            median_cpu = statistics.median(cpu_times)
            median_rss = statistics.median(rss_peaks)
            median_merge = statistics.median(merge_times)


            if executor == "serial" and workers == 1:
                baseline_wall = median_wall

            speedup = baseline_wall / median_wall if baseline_wall else 1.0

            results.append({
                "executor": executor,
                "workers": workers,
                "wall": median_wall,
                "cpu": median_cpu,
                "rss": median_rss,
                "merge": median_merge,
                "speedup": speedup,
            })
            print(f"[{executor.upper():9} | W:{workers}] -> Wall: {median_wall:.2f}s | Speedup: {speedup:.2f}x")


    print("\n" + "=" * 85)
    print(
        f"{'Executor':<10} | {'Workers':<7} | {'Wall (s)':<10} | {'CPU (s)':<10} | {'Peak RSS':<10} | {'Merge (s)':<10} | {'Speedup':<8}")
    print("-" * 85)
    for r in results:
        print(
            f"{r['executor']:<10} | {r['workers']:<7} | {r['wall']:<10.2f} | {r['cpu']:<10.2f} | {r['rss']:<9.1f}M | {r['merge']:<10.2f} | {r['speedup']:<7.2f}×")
    print("=" * 85)


    plt.figure(figsize=(10, 6))

    for executor in executors:
        exec_data = [r for r in results if r['executor'] == executor]
        if not exec_data:
            continue
        ws = [r['workers'] for r in exec_data]
        su = [r['speedup'] for r in exec_data]
        plt.plot(ws, su, marker='o', linewidth=2, label=f"{executor}")


    max_w = max(workers_list)
    plt.plot([1, max_w], [1, max_w], linestyle='--', color='gray', label="Ideal Linear")

    plt.xlabel("Workers", fontsize=12)
    plt.ylabel("Speedup (×)", fontsize=12)
    plt.title("Concurrency Speedup Comparison (Index Building)", fontsize=14)
    plt.legend()
    plt.grid(True, linestyle=":", alpha=0.7)

    chart_path = Path("speedup_chart.png")
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"\n📊 Графік успішно збережено у файл: {chart_path.absolute()}")
    plt.close()


if __name__ == "__main__":
    run_benchmark()