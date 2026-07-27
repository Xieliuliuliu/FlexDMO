import os
import time
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from scipy.stats import ranksums

from utils.metrics import calculate_MIGD
from utils.result_io import load_result_from_files


def extract_info_from_settings(settings):
    """Return the algorithm, problem, and dynamic-environment identifiers."""
    response = settings.get("response_strategy_class", "Unknown")
    search = settings.get("search_algorithm_class", "Unknown")
    problem = settings.get("problem_class", "Unknown")
    problem_params = settings.get("problem_params", {})
    return response, search, problem, problem_params.get("n"), problem_params.get("tau")


def find_first_and_second(mean_list):
    """Return indexes of the smallest and second-smallest finite values."""
    ordered = sorted(
        ((value, index) for index, value in enumerate(mean_list) if value is not None),
        key=lambda pair: pair[0],
    )
    if not ordered:
        return None, None
    return ordered[0][1], ordered[1][1] if len(ordered) > 1 else None


def rank_sums_test(alg_data1, alg_data2):
    """Return whether two non-empty samples differ at alpha=0.05."""
    if not alg_data1 or not alg_data2:
        return False
    _, p_value = ranksums(alg_data1, alg_data2)
    return bool(p_value < 0.05)


def _algorithm_label(algorithm):
    return f"{algorithm[0]}-{algorithm[1]}"


def run(config):
    """Calculate MIGD values and write a comparison workbook."""
    input_paths = config["input_paths"]
    output_path = config["output_path"]
    your_algorithm = config.get("your_algorithm", "")

    results = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    loaded_count = 0
    for result in load_result_from_files(input_paths):
        settings = result.get("settings", {})
        response, search, problem, n, tau = extract_info_from_settings(settings)
        results[response][search][problem][(n, tau)].append(
            calculate_MIGD(result["runtime_populations"])
        )
        loaded_count += 1

    if loaded_count == 0:
        raise ValueError("No valid result files were loaded.")

    algorithms = sorted(
        {(response, search) for response in results for search in results[response]},
        key=_algorithm_label,
    )
    if your_algorithm:
        for index, algorithm in enumerate(algorithms):
            if _algorithm_label(algorithm) == your_algorithm:
                algorithms.insert(0, algorithms.pop(index))
                break

    cases = sorted(
        {
            (problem, environment)
            for response, search in algorithms
            for problem, environment_map in results[response][search].items()
            for environment in environment_map
        },
        key=lambda case: (case[0], str(case[1])),
    )

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "MIGD"
    worksheet.cell(1, 1, "Problem")
    worksheet.cell(1, 2, "(n, tau)")
    for column, algorithm in enumerate(algorithms, start=3):
        worksheet.cell(1, column, _algorithm_label(algorithm))

    rank_sums_collection = [
        {"win": 0, "loss": 0, "eq": 0} for _ in range(max(0, len(algorithms) - 1))
    ]
    best_fill = PatternFill(start_color="909090", end_color="909090", fill_type="solid")
    second_fill = PatternFill(start_color="CBCBCB", end_color="CBCBCB", fill_type="solid")

    for row, (problem, environment) in enumerate(cases, start=2):
        worksheet.cell(row, 1, problem)
        worksheet.cell(row, 2, str(environment))
        samples = [
            results[response][search].get(problem, {}).get(environment, [])
            for response, search in algorithms
        ]
        means = [sum(values) / len(values) if values else None for values in samples]
        target_values = samples[0] if samples else []
        target_mean = means[0] if means else None

        for index, (values, mean) in enumerate(zip(samples, means)):
            if mean is None:
                continue
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            compare_mark = ""
            if index > 0 and target_mean is not None:
                if rank_sums_test(target_values, values):
                    if target_mean > mean:
                        rank_sums_collection[index - 1]["loss"] += 1
                        compare_mark = "-"
                    else:
                        rank_sums_collection[index - 1]["win"] += 1
                        compare_mark = "+"
                else:
                    rank_sums_collection[index - 1]["eq"] += 1
                    compare_mark = "~"
            worksheet.cell(row, 3 + index, f"{mean:.3e}({variance:.3e}){compare_mark}")

        best_index, second_index = find_first_and_second(means)
        if best_index is not None:
            worksheet.cell(row, 3 + best_index).fill = best_fill
        if second_index is not None:
            worksheet.cell(row, 3 + second_index).fill = second_fill

    summary_row = len(cases) + 2
    worksheet.cell(summary_row, 1, "+/~/-")
    worksheet.cell(summary_row, 1).alignment = Alignment(horizontal="center")
    worksheet.merge_cells(
        start_row=summary_row, start_column=1, end_row=summary_row, end_column=2
    )
    for index in range(len(algorithms)):
        if index == 0:
            value = "-"
        else:
            comparison = rank_sums_collection[index - 1]
            value = f"{comparison['win']}/{comparison['eq']}/{comparison['loss']}"
        worksheet.cell(summary_row, 3 + index, value)

    worksheet.freeze_panes = "C2"
    worksheet.column_dimensions["A"].width = 18
    worksheet.column_dimensions["B"].width = 14
    for column in range(3, 3 + len(algorithms)):
        worksheet.column_dimensions[worksheet.cell(1, column).column_letter].width = 28

    os.makedirs(output_path, exist_ok=True)
    output_file = os.path.join(output_path, f"MIGD_comparison_{int(time.time())}.xlsx")
    workbook.save(output_file)
    print(f"Results saved to: {output_file}")
    return output_file
