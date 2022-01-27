from bosses import optionalBosses, allBosses
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
    print(boss.name + '\n')
    if not boss.convertToMarkovChain():
        print(boss.name, 'State space too large\n')
        return
    print(boss.name, 'created matrix')
    (x, cdf, pdf, mode, half, average, xcutoff) = boss.getAbsorbingMatrixGraph()
    print(boss.name, 'created datapoints')

    
    lootstring = ''
    count = 0
    items = [f"{item.title()}: {amount}" for item, amount in boss.loot_amount.items() if amount > 0]
    for it,part in enumerate(items):
        lootstring = f"{lootstring} {part}{', ' if it < len(items) - 1 else ''}"
        count += len(part)
        if count >= 70:
            lootstring = f"{lootstring}\n"
            count = 0
    
    _, (ax) = plt.subplots()
    kc_name = boss.kc_name
    #axis labels
    ax.set_xlabel(f"{kc_name}\n\n{kc_name} it takes to get:\n {lootstring}")

    ax2 = ax.twinx()
    legend = ax.twinx()
    legend.axes.yaxis.set_visible(False)
    
    #data points
    whitespace = 1.02

    ax2.plot(x,cdf, label='cdf', color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.set_ylabel('% chance to complete at or before kc', color='tab:red')
    ax2.set_ylim(bottom=0, top=100 * whitespace)
    ax.plot(x,pdf, label='pdf', color='tab:blue')
    ax.set_ylabel('% chance to complete at kc', color='tab:blue')

    try:
        ax.tick_params(axis='y', labelcolor='tab:blue')
        ax.set_ylim(bottom=0, top=max(pdf) * whitespace)
    
        if(mode - xcutoff < len(x)):
            legend.axvline(x=mode, ymax=(max(cdf[mode - xcutoff]/max(cdf), pdf[mode - xcutoff]/max(pdf)) / whitespace), linestyle='--', color="gray", label=f"Mode: {mode} {kc_name}")
        if(half - xcutoff< len(x)):
            legend.axvline(x=half, ymax=(max(cdf[half - xcutoff]/max(cdf), pdf[half - xcutoff]/max(pdf)) / whitespace), linestyle='-', color="gray", label=f"Median: {half} {kc_name}")
        # average is an floating point number
        if(int(average) - xcutoff < len(x)):
            legend.axvline(x=average, ymax=(max(cdf[int(average) - xcutoff]/max(cdf), pdf[int(average) - xcutoff]/max(pdf)) / whitespace), linestyle='-.', color="gray", label=f"Mean: {average:.2f} {kc_name}")
    except Exception as e:
        print(boss.name, e)
    
    ax.set_title(f"Chance to complete {boss.name.replace('_', ' ').capitalize()}")
    legend.legend(loc='center right')

    ax.set_xlim(left=x[0], right=x[-1])

    plt.savefig(f"images/groupsize{boss.group_size}/{boss.name.strip().lower()}.png", bbox_inches='tight')
    plt.close()



if __name__ == '__main__':
    bosses = []

    for i in range(1,6):
        for boss in allBosses() + optionalBosses():
            boss.set_groupsize(i)
            bosses.append(boss)

    # doing long bosses first allows the shorter bosses to fill in the 'gaps' after a thread has finished better
    # leading to shorter execution times. States is a good indication of how long a boss will take to compute
    bosses.sort(key=lambda b: b.nStates, reverse = True)
    print(len(bosses))

    pool = Pool(processes=pool_size)
    # chunksize 1 ensures the bosses get evaluated rougly in the same order as the bosses array which is good enough
    pool.map(createCompletionPlot, bosses, chunksize=1)
