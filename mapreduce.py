"""Small, educational MapReduce word counter.

The number of mappers (split threads) and reducers is configurable. After the
reducers finish, their outputs are merged into one alphabetically sorted file
called ``final_output.txt``.
"""

import argparse  # for command-line argument parsing
import re  # for regular expressions
import time  # for timing a run
from itertools import islice
from pathlib import Path  # for working with file paths
from threading import Thread


DEFAULT_MAPPERS = None  # None means "one mapper per input file"
DEFAULT_REDUCERS = 2
FINAL_OUTPUT_NAME = "final_output.txt"
WORD_PATTERN = re.compile(r"[a-z]+")


def count_lines(path):
    """Count the lines in one input file without loading it into memory."""
    with path.open(encoding="utf-8") as source:
        return sum(1 for _ in source)


def build_splits(files, num_mappers):
    """Divide all input lines into ``num_mappers`` contiguous splits.

    Each split is a list of ``(path, start_line, end_line)`` ranges. Splitting
    inside a file lets the user choose more mappers than there are input files.
    The mapper count is reduced when there are fewer lines than mappers.
    """
    file_counts = [(path, count_lines(path)) for path in files]
    total_lines = sum(count for _, count in file_counts)
    if total_lines == 0:
        # Empty input is still a valid job: one mapper reads nothing and every
        # reducer writes an empty output file.
        return [[]], 0

    num_mappers = max(1, min(num_mappers, total_lines))
    splits = [[] for _ in range(num_mappers)]

    offset = 0
    for path, line_count in file_counts:
        local_start = 0
        while local_start < line_count:
            first_global_line = offset + local_start
            split_id = (first_global_line * num_mappers) // total_lines
            next_boundary = (
                ((split_id + 1) * total_lines + num_mappers - 1) // num_mappers
            )
            local_end = min(line_count, next_boundary - offset)
            splits[split_id].append((path, local_start, local_end))
            local_start = local_end
        offset += line_count

    return splits, total_lines


def map_ranges(ranges):
    """Map: read one split and emit (word, 1) for each occurrence."""
    for path, start_line, end_line in ranges:
        with path.open(encoding="utf-8") as source:
            for line in islice(source, start_line, end_line):
                for word in WORD_PATTERN.findall(line.lower()):
                    yield word, 1


def combine(pairs):
    """Combine: count repeated words inside this split only."""
    subtotals = {}
    for word, value in pairs:
        subtotals[word] = subtotals.get(word, 0) + value
    return subtotals


def reducer_for(word, num_reducers=DEFAULT_REDUCERS):
    """Choose a reducer using a stable hash (Python's hash() varies per run)."""
    return sum(ord(letter) for letter in word) % num_reducers


def partition(subtotals, num_reducers=DEFAULT_REDUCERS):
    """Partition: assign each local subtotal to exactly one reducer."""
    buckets = [[] for _ in range(num_reducers)]
    for word, count in subtotals.items():
        buckets[reducer_for(word, num_reducers)].append((word, count))
    return buckets


def run_mapper(ranges, index, num_reducers, results, errors):
    try:
        results[index] = partition(combine(map_ranges(ranges)), num_reducers)
    except Exception as error:
        errors[index] = error


def shuffle_and_sort(mapper_results, num_reducers=DEFAULT_REDUCERS):
    """Shuffle: gather matching partitions; sort and group by word."""
    shuffled = []
    for reducer_id in range(num_reducers):
        pairs = []
        for buckets in mapper_results:
            pairs.extend(buckets[reducer_id])
        pairs.sort(key=lambda pair: pair[0])

        groups = {}
        for word, count in pairs:
            if word not in groups:
                groups[word] = []
            groups[word].append(count)
        shuffled.append(groups)
    return shuffled


def reduce_words(groups, output_file):
    """Reduce: sum each word's subtotals and write sorted output."""
    with output_file.open("w", encoding="utf-8") as output:
        for word in sorted(groups):
            total = sum(groups[word])
            output.write(f"{word}\t{total}\n")


def merge_reducer_outputs(reducer_files, final_file):
    """Merge every reducer output into one alphabetically sorted file."""
    totals = {}
    for reducer_file in reducer_files:
        with reducer_file.open(encoding="utf-8") as source:
            for line in source:
                word, _, count = line.rstrip("\n").partition("\t")
                if not word:
                    continue
                totals[word] = totals.get(word, 0) + int(count)

    with final_file.open("w", encoding="utf-8") as output:
        for word in sorted(totals):
            output.write(f"{word}\t{totals[word]}\n")
    return totals


def run(input_dir, output_dir, num_mappers=None, num_reducers=DEFAULT_REDUCERS,
        progress=None):
    """Run the full MapReduce job and return a dictionary of run statistics.

    ``progress`` is an optional callable that receives human-readable status
    strings; the GUI uses it to fill its log panel.
    """
    report = progress if progress is not None else (lambda message: None)
    started_at = time.perf_counter()

    if num_reducers < 1:
        raise ValueError("The number of reducers must be at least 1.")

    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if not input_dir.is_dir():
        raise ValueError(f"Input folder does not exist: {input_dir}")
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("Input and output folders must be different.")

    input_files = sorted(path for path in input_dir.glob("*.txt") if path.is_file())
    if not input_files:
        raise ValueError(f"No .txt files found in {input_dir}")

    requested_mappers = len(input_files) if num_mappers is None else num_mappers
    if requested_mappers < 1:
        raise ValueError("The number of mappers must be at least 1.")
    splits, total_lines = build_splits(input_files, requested_mappers)
    num_mappers = len(splits)

    report(f"Found {len(input_files)} input file(s) with {total_lines} line(s).")
    report(f"Created {num_mappers} mapper split(s) and {num_reducers} reducer(s).")

    results = [None] * num_mappers
    errors = [None] * num_mappers
    # Create exactly one mapper thread per split, then start all of them.
    threads = [
        Thread(
            target=run_mapper,
            args=(splits[index], index, num_reducers, results, errors),
            name=f"mapper-{index}",
        )
        for index in range(num_mappers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()  # All mapper results must be ready before shuffle.
    for index, error in enumerate(errors):
        if error is not None:
            raise RuntimeError(f"Mapper {index} failed: {error}") from error

    report("All mapper threads finished. Shuffling and sorting...")
    shuffled = shuffle_and_sort(results, num_reducers)

    output_dir.mkdir(parents=True, exist_ok=True)
    # Remove reducer files left over from an earlier run with more reducers.
    for stale_file in output_dir.glob("reducer_*.txt"):
        if stale_file.is_file():
            stale_file.unlink()

    reducer_files = []
    for reducer_id, groups in enumerate(shuffled):
        output_file = output_dir / f"reducer_{reducer_id}.txt"
        reduce_words(groups, output_file)
        reducer_files.append(output_file)
        report(f"Reducer {reducer_id}: {len(groups)} unique word(s) -> {output_file.name}")

    report(f"Merging {num_reducers} reducer output file(s)...")
    final_file = output_dir / FINAL_OUTPUT_NAME
    totals = merge_reducer_outputs(reducer_files, final_file)

    elapsed = time.perf_counter() - started_at
    report(f"Finished in {elapsed:.2f}s. Final output: {final_file}")

    return {
        "input_files": len(input_files),
        "lines": total_lines,
        "mappers": num_mappers,
        "reducers": num_reducers,
        "unique_words": len(totals),
        "total_words": sum(totals.values()),
        "reducer_files": [str(path) for path in reducer_files],
        "final_output": str(final_file),
        "seconds": elapsed,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Educational MapReduce word count with a merged final output."
    )
    parser.add_argument("input_dir", nargs="?", default="input")
    parser.add_argument("output_dir", nargs="?", default="output")
    parser.add_argument(
        "-m", "--mappers", type=int, default=DEFAULT_MAPPERS,
        help="number of mapper threads/splits (default: one per input file)",
    )
    parser.add_argument(
        "-r", "--reducers", type=int, default=DEFAULT_REDUCERS,
        help=f"number of reducers (default: {DEFAULT_REDUCERS})",
    )
    args = parser.parse_args(argv)

    try:
        stats = run(
            args.input_dir,
            args.output_dir,
            num_mappers=args.mappers,
            num_reducers=args.reducers,
            progress=print,
        )
    except (ValueError, OSError, UnicodeError, RuntimeError) as error:
        parser.exit(1, f"Error: {error}\n")

    print(
        f"Summary: {stats['mappers']} mapper(s), {stats['reducers']} reducer(s), "
        f"{stats['unique_words']} unique word(s), {stats['total_words']} total word(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
