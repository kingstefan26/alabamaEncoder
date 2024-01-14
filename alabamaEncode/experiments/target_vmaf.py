import json


def get_predone():
    obj = json.load(
        open(
            "/home/kokoniara/.config/JetBrains/PyCharm2023.2/scratches/scratch_15.json"
        )
    )
    [c.update({"crf": i}) for i, c in enumerate(obj)]
    # remove ssim total_fps target_miss_proc rate_search_time basename version
    [c.pop("ssim") for c in obj]
    [c.pop("total_fps") for c in obj]
    [c.pop("target_miss_proc") for c in obj]
    [c.pop("rate_search_time") for c in obj]
    [c.pop("basename") for c in obj]
    [c.pop("version") for c in obj]
    [c.pop("chunk_index") for c in obj]
    return obj


if __name__ == "__main__":
    d = get_predone()

    target_vmaf = 95

    def get_score(crf):
        def point_to_score(p):
            """
            calc score including bitrate vmaf and 1% 5% percentiles with weights
            to get the smallest video but with reasonable vmaf and 5% vmaf scores
            """

        for c in d:
            if c["crf"] == crf:
                score = 0

                score_bellow_target_weight = float(0)  # 7
                score_above_target_weight = float(0)  # 4
                score_bitrate_weight = float(0)  # 15
                score_average_weight = float(0)  # 2
                score_5_percentile_target_weight = float(1)  # 5

                # punish if the score is bellow target
                weight = max(0, target_vmaf - c["vmaf"]) * score_bellow_target_weight
                score += weight

                # punish if the score is higher then target
                target_weight = (
                    max(0, c["vmaf"] - target_vmaf) * score_above_target_weight
                )
                score += target_weight

                # how 5%tile frames looked compared to overall score
                # punishing if the video is not consistent
                average_weight = abs(c["vmaf_avg"] - c["vmaf"]) * score_average_weight
                score += average_weight

                # how 5%tile frames looked compared to target, don't if above target
                # punishing if the worst parts of the video are bellow target
                weight_ = (
                    abs(target_vmaf - c["vmaf_percentile_5"])
                    * score_5_percentile_target_weight
                )
                print(crf, weight_)
                score += weight_

                # we punish the hardest for bitrate
                bitrate_weight = max(1, (c["bitrate"] / 100)) * score_bitrate_weight
                score += bitrate_weight  # bitrate

                return score

    def opt_optuna(_get_score, max_probes) -> int:
        import optuna

        def objective(trial):
            value = trial.suggest_int("value", 0, 60)
            return _get_score(value)

        # quiet logs to 0
        # optuna.logging.set_verbosity(0)
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=max_probes)
        result = study.best_params["value"]

        return int(result)

    def opt_primitive() -> int:
        closest_score = float("inf")
        best_crf = -1

        for crf in range(15, 60):
            # score = get_score(crf)
            for c in d:
                if c["crf"] == crf:
                    score = abs(target_vmaf - c["vmaf_percentile_5"])
                    print(f"closest_score: {closest_score}, crf: {crf}, score: {score}")
                    if score < closest_score:
                        closest_score = score
                        best_crf = crf
        return best_crf

    # a = opt_optuna(get_score, 2)
    # for c in d:
    #     if c["crf"] == a:
    #         print(c)
    # print(a)
    a = opt_primitive()
    for c in d:
        if c["crf"] == a:
            print(c)
    print(a)

    # plt of vmaf to crf
    import matplotlib.pyplot as plt

    x = [c["crf"] for c in d]
    y = [c["vmaf_percentile_5"] for c in d]

    plt.plot(x, y)
    plt.xlabel("crf")
    plt.ylabel("vmaf_percentile_5")
    # dot where crf touches the line
    plt.plot(a, target_vmaf, "ro")
    plt.show()
    plt.savefig("vmaf_crf.png")
