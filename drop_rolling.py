from bosses import all_bosses, complete_drops
import functools
import random
import math
import multiprocessing
import concurrent.futures
import matplotlib.pyplot as plt
from collections import Counter

number_off_completions = 1000000
    
def calc_average_completion(boss, sample_size):
    completions = []

    for _ in range(sample_size):
        kc, _ = boss.complete()
        completions += [kc]

    average_completion = sum(completions)/len(completions)
    print("{},{},{},{},{}".format(boss.name,average_completion,min(completions),max(completions),sorted(completions)[int(len(completions)/2)]))
    
    c = Counter(completions)
    x = sorted(list(c.keys()))
    y = [c[it] for it in x]

    _, ax = plt.subplots()
    #axis labels
    ax.set_ylabel('number of completions')
    ax.set_xlabel('kc')
    
    #data points
    ax.plot(x,y, 'o', markersize=1, label='boss completion')
    
    #lines at relevant points
    half = sorted(completions)[int(len(completions)/2)]
    ax.axvline(x=half, color='r', label="50% of people completed at {} kc".format(half))
    ax.axvline(x=average_completion, color='g', label="average completion at {} kc".format(int(average_completion)+1))
    
    #title
    ax.set_title("{} completions of {}".format(sample_size, boss.name))
    ax.legend()
    plt.savefig("images/{}_{}.pdf".format(sample_size, boss.name, bbox_inches='tight'))


if __name__ == '__main__':
    bosses = all_bosses + complete_drops

    for boss in bosses:
        print(boss.name)

    calc_average_completion(bosses[0], number_off_completions)
    executor = concurrent.futures.ProcessPoolExecutor(10)
    futures = [executor.submit(calc_average_completion, boss, number_off_completions) for boss in bosses]

    concurrent.futures.wait(futures)
