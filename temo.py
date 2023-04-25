
if __name__ == '__main__':

    a = "| 8-15        | 3063kb | 2938 | 94.66 |\n| 0-15        | 3128kb | 3000 | 94.84 |\n| 0-8         | 3154kb | 3024 | 94.84 |\n| disabled    | 3072kb | 2946 | 94.55 |"

    dic = {
        "8-15": -1,
        "0-15": -1,
        "0-8": -1,
        "disabled": -1,
    }

    # db rate = size / vmaf

    for line in a.splitlines():
        if line.startswith("|"):
            print(line)
            line = line.split("|")
            line = [x.strip() for x in line if x.strip()]
            line = [x.replace("kb", "") for x in line]

            # line = name, size, rate, vmaf
            # save db rate to dict with the matching name
            dic[line[0]] = int(line[1]) / float(line[3])


    print(dic)

    # calc procent cahnges for each name compared to disabled, rounded to 2 places
    for key in dic:
        if key != "disabled":
            print(key, ((dic["disabled"] - dic[key]) / dic["disabled"] * 100).__round__(2), "%")



