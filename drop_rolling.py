from bosses import all_bosses, complete_drops
import concurrent.futures
import matplotlib
from collections import Counter
from multiprocessing import Pool
matplotlib.use('agg')
import matplotlib.pyplot as plt

pool_size = 10
number_off_completions = 1000000
    
def calc_average_completion(boss, sample_size=number_off_completions):
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

def createCompletionPlot(boss):
    boss.convertToMarkovChain()
    (x,y, median, half, average) = boss.getAbsorbingMatrixGraph()
    
    _, ax = plt.subplots()
    #axis labels
    ax.set_ylabel('% chance of completion')
    ax.set_xlabel('kc')
    
    #data points
    ax.plot(x,y, label='boss completion')
    

    ax.axvline(x=median, color='b', label="Most people complete at {} kc".format(median))
    ax.axvline(x=half, color='r', label="50% of people complete before {} kc".format(half))
    ax.axvline(x=average, color='g', label="average completion at {} kc".format(int(average)+1))
    ax.set_title("odds of completing {}".format(boss.name))
    ax.legend()

    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0, right=x[-1])

    plt.savefig("images/{}.pdf".format(boss.name, bbox_inches='tight'))

if __name__ == '__main__':
    bosses = all_bosses + complete_drops

    
    for boss in bosses:
        print(boss.name)

    pool = Pool(processes=pool_size)
    pool.map(createCompletionPlot, bosses)
