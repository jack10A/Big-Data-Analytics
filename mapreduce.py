"""A small word-count MapReduce engine using only Python's standard library."""

import argparse #for command-line argument parsing
import re #for regular expressions
from pathlib import Path #for working with file paths
from threading import Thread


NUM_REDUCERS = 2


def map_words(split):
    """Map: read one file and emit (word, 1) for each occurrence."""
    with split.open(encoding="utf-8") as source:
        for line in source:
            for word in re.findall(r"[a-z]+", line.lower()):
                yield word, 1


def combine(pairs):
    """Combine: count repeated words inside this split only."""
    subtotals = {}
    for word, value in pairs:
        subtotals[word] = subtotals.get(word, 0) + value
    return subtotals


def reducer_for(word):
    # Stable across runs: Python's built-in hash() can change between runs.
    return sum(ord(letter) for letter in word) % NUM_REDUCERS


def partition(subtotals):
    """Partition: assign each local subtotal to exactly one reducer."""
    buckets = [[] for _ in range(NUM_REDUCERS)]
    for word, count in subtotals.items():
        buckets[reducer_for(word)].append((word, count))
    return buckets


def run_mapper(split, index, results, errors):
    try:
        results[index] = partition(combine(map_words(split)))
    except Exception as error:
        errors[index] = error


def shuffle_and_sort(mapper_results):
    """Shuffle: gather matching partitions; sort and group by word."""
    shuffled = []
    for reducer_id in range(NUM_REDUCERS):
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
        for word, values in groups.items():
            total = 0
            for value in values:
                total += value
            output.write(f"{word}\t{total}\n")


def run(input_dir, output_dir):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if not input_dir.is_dir():
        raise ValueError(f"Input folder does not exist: {input_dir}")
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("Input and output folders must be different.")
    splits = sorted(path for path in input_dir.glob("*.txt") if path.is_file())
    if not splits:
        raise ValueError(f"No .txt files found in {input_dir}")

    results = [None] * len(splits)
    errors = [None] * len(splits)
    # Create exactly one mapper thread per input file, then start all of them.
    threads = [
        Thread(target=run_mapper, args=(split, index, results, errors))
        for index, split in enumerate(splits)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()  # All mapper results must be ready before shuffle.
    for error in errors:
        if error is not None:
            raise error

    shuffled = shuffle_and_sort(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    for reducer_id, groups in enumerate(shuffled):
        output_file = output_dir / f"reducer_{reducer_id}.txt"
        reduce_words(groups, output_file)
        print(f"Reducer {reducer_id}: {len(groups)} unique words -> {output_file}")
    print(f"Finished: {len(splits)} mapper threads, {NUM_REDUCERS} reducers.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", default="input")
    parser.add_argument("output_dir", nargs="?", default="output")
    args = parser.parse_args()
    try:
        run(args.input_dir, args.output_dir)
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(1, f"Error: {error}\n")
