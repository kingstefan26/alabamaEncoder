import math
import random
from typing import List

from alabamaEncode.core.chunk_job import ChunkEncoder


def total_length(scenes: List[ChunkEncoder]) -> int:
    return sum(scene.chunk.length for scene in scenes)


def get_variance(scenes: List[ChunkEncoder]) -> float:
    avg_length = total_length(scenes) / len(scenes)
    variance = sum((scene.chunk.length - avg_length) ** 2 for scene in scenes) / len(
        scenes
    )
    return variance


def annealing(scenes: List[ChunkEncoder], iterations: int) -> List[ChunkEncoder]:
    current_solution = scenes.copy()
    best_solution = scenes.copy()
    temperature = 1.0
    cooling_rate = 0.95

    for _ in range(iterations):
        neighbor_solution = current_solution.copy()

        # Swap two random scenes
        idx1, idx2 = random.sample(range(len(neighbor_solution)), 2)
        neighbor_solution[idx1], neighbor_solution[idx2] = (
            neighbor_solution[idx2],
            neighbor_solution[idx1],
        )

        # Calculate the variance of current and neighbor solutions
        current_variance = get_variance(current_solution)
        neighbor_variance = get_variance(neighbor_solution)

        # Calculate the change in variance
        delta_variance = neighbor_variance - current_variance

        # Accept the neighbor solution if it's better or according to the temperature and a random probability
        if delta_variance < 0 or random.uniform(0, 1) < math.exp(
            -delta_variance / temperature
        ):
            current_solution = neighbor_solution

        # Update the best solution
        if get_variance(current_solution) < get_variance(best_solution):
            best_solution = current_solution

        # Cool down the temperature
        temperature *= cooling_rate

    return best_solution
