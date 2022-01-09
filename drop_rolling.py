from logging import error
from bosses import all_bosses, complete_drops
import matplotlib
from collections import Counter
from multiprocessing import Pool
matplotlib.use('agg')
import matplotlib.pyplot as plt

pool_size = 10
number_off_completions = 1000000
    
def simulate_average_completion(boss, sample_size=number_off_completions):
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
    # print(boss.name)
    boss.convertToMarkovChain()
    # print(boss.name, 'created matrix')
    (x, cdf, pdf, mode, half, average) = boss.getAbsorbingMatrixGraph()
    # print(boss.name, 'created datapoints')
    
    _, (ax) = plt.subplots()
    #axis labels
    ax.set_xlabel('kc')

    ax2 = ax.twinx()
    legend = ax.twinx()
    legend.axes.yaxis.set_visible(False)
    
    #data points
    whitespace = 1.02

    ax2.plot(x,cdf, label='cdf', color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.set_ylabel('% chance to have completed', color='tab:red')
    ax2.set_ylim(bottom=0, top=100 * whitespace)
    ax.plot(x,pdf, label='pdf', color='tab:blue')
    ax.set_ylabel('% chance to complete at kc', color='tab:blue')
    ax.tick_params(axis='y', labelcolor='tab:blue')
    ax.set_ylim(bottom=0, top=max(pdf) * whitespace)
    
    kc_name = boss.kc_name

    try:
        if(mode < len(x)):
            legend.axvline(x=mode, ymax=(max(cdf[mode]/max(cdf), pdf[mode]/max(pdf)) / whitespace), linestyle='--', color="gray", label=f"Mode {mode} {kc_name}")
        if(half < len(x)):
            legend.axvline(x=half, ymax=(max(cdf[half]/max(cdf), pdf[half]/max(pdf)) / whitespace), linestyle='-', color="gray", label=f"Median {half} {kc_name}")
        # average is an floating point number
        if(int(average) < len(x)):
            legend.axvline(x=average, ymax=(max(cdf[int(average)]/max(cdf), pdf[int(average)]/max(pdf)) / whitespace), linestyle='-.', color="gray", label=f"Mean: {kc_name} {average:.2f}")
    except(error):
        print(boss.name, mode)
    
    ax.set_title(f"Chance to complete {boss.name.replace('_', ' ').capitalize()}")
    legend.legend(loc='center right')

    ax.set_xlim(left=0, right=x[-1])

    plt.savefig(f"images/{boss.name.strip()}.pdf", bbox_inches='tight')

if __name__ == '__main__':
    bosses = all_bosses + complete_drops

    pool = Pool(processes=pool_size)
    pool.map(createCompletionPlot, bosses)
