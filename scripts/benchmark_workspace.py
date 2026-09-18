"""Milestone 5 Performance Benchmarks for OpenRobo Workspace Generator."""

import statistics
import time

from openrobo_schemas import validate_stack_manifest
from openrobo_workspace import WorkspaceGenerator, WorkspacePlanner


def generate_benchmark_manifest(num_resources: int) -> dict:
    known_adapters = ["nav2", "slam_toolbox", "ros2_control", "gazebo"]
    resources = []
    for i in range(num_resources):
        if i < len(known_adapters):
            rid = known_adapters[i]
            rname = rid.replace("_", " ").title()
        else:
            rid = f"sensor_module_{i}"
            rname = f"Sensor Module {i}"
        resources.append(
            {
                "id": rid,
                "name": rname,
                "version": f"1.{i}.0",
                "category": "sensors" if i >= len(known_adapters) else "general",
            }
        )

    return {
        "id": f"benchmark_stack_{num_resources}",
        "name": f"Benchmark Stack {num_resources}",
        "description": f"Benchmark stack containing {num_resources} resources",
        "target": {
            "ros_distro": "humble",
            "os": "ubuntu-22.04",
            "architecture": "x86_64",
        },
        "resources": resources,
    }


def run_benchmark(num_resources: int, iterations: int = 20):
    manifest = generate_benchmark_manifest(num_resources)

    # 1. Validation benchmark
    val_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        validate_stack_manifest(manifest)
        val_times.append((time.perf_counter() - t0) * 1000)

    # 2. Planning benchmark
    plan_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        planner = WorkspacePlanner(manifest)
        planner.plan()
        plan_times.append((time.perf_counter() - t0) * 1000)

    # 3. File generation benchmark
    gen_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        gen = WorkspaceGenerator(manifest)
        plan, files = gen.generate_files()
        gen_times.append((time.perf_counter() - t0) * 1000)

    # 4. ZIP archive creation benchmark
    zip_times = []
    zip_sizes = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        gen = WorkspaceGenerator(manifest)
        zip_bytes = gen.export_archive()
        zip_times.append((time.perf_counter() - t0) * 1000)
        zip_sizes.append(len(zip_bytes))

    print(f"\n================ BENCHMARK: {num_resources} RESOURCES ({iterations} runs) ================")
    print(f"File count generated: {len(files)} files | Archive size: {zip_sizes[0]:,} bytes")
    print(
        f"Validation: mean={statistics.mean(val_times):.2f}ms, median={statistics.median(val_times):.2f}ms, "
        f"min={min(val_times):.2f}ms, max={max(val_times):.2f}ms"
    )
    print(
        f"Planning:   mean={statistics.mean(plan_times):.2f}ms, median={statistics.median(plan_times):.2f}ms, "
        f"min={min(plan_times):.2f}ms, max={max(plan_times):.2f}ms"
    )
    print(
        f"Generation: mean={statistics.mean(gen_times):.2f}ms, median={statistics.median(gen_times):.2f}ms, "
        f"min={min(gen_times):.2f}ms, max={max(gen_times):.2f}ms"
    )
    print(
        f"ZIP Export: mean={statistics.mean(zip_times):.2f}ms, median={statistics.median(zip_times):.2f}ms, "
        f"min={min(zip_times):.2f}ms, max={max(zip_times):.2f}ms"
    )


if __name__ == "__main__":
    for count in [10, 25, 50]:
        run_benchmark(count, iterations=30)
