import time
import statistics
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def simulated_disk_read(file_path: str) -> int:
    """Імітація блокуючої операції введення-виводу (I/O) з диска або мережі."""
    time.sleep(0.01)  # 10мс затримки на кожне «читання»
    return len(file_path)

def run_io_benchmark():
    paths = [f"doc_{i}.txt" for i in range(100)]
    runs = 3
    workers_list = [1, 2, 4, 8, 16]
    executors = ["serial", "threads", "processes"]

    results = []
    baseline_wall = None

    print(f"📁 Запуск I/O бенчмарку для {len(paths)} задач (імітація затримки 10мс на задачу)...\n")

    for executor_type in executors:
        for workers in workers_list:
            if executor_type == "serial" and workers > 1:
                continue

            wall_times = []

            for _ in range(runs):
                start_wall = time.perf_counter()

                if executor_type == "serial":
                    [simulated_disk_read(p) for p in paths]
                elif executor_type == "threads":
                    with ThreadPoolExecutor(max_workers=workers) as executor:
                        list(executor.map(simulated_disk_read, paths))
                elif executor_type == "processes":
                    with ProcessPoolExecutor(max_workers=workers) as executor:
                        list(executor.map(simulated_disk_read, paths))

                end_wall = time.perf_counter()
                wall_times.append(end_wall - start_wall)

            median_wall = statistics.median(wall_times)

            if executor_type == "serial" and workers == 1:
                baseline_wall = median_wall

            speedup = baseline_wall / median_wall if baseline_wall else 1.0

            results.append({
                "executor": executor_type,
                "workers": workers,
                "wall": median_wall,
                "speedup": speedup,
            })
            print(f"[{executor_type.upper():9} | W:{workers}] -> Wall Time: {median_wall:.3f}s | Speedup: {speedup:.2f}×")


    print("\n" + "=" * 65)
    print(f"{'Executor':<12} | {'Workers':<8} | {'Wall Time (s)':<15} | {'Speedup':<8}")
    print("-" * 65)
    for r in results:
        print(f"{r['executor']:<12} | {r['workers']:<8} | {r['wall']:<15.3f} | {r['speedup']:<7.2f}×")
    print("=" * 65)

if __name__ == "__main__":
    run_io_benchmark()