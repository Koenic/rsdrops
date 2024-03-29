import functools
from operator import mul
from functools import reduce
import random
import math
from scipy.sparse import coo_matrix
import numpy as np

class monster:
    loot_odds = {}
    secondary_odds = {}
    tertiary_odds = {}
    quaternary_odds = {}
    kc_name = 'kc'

    def __init__(self, loot_tables=None, loot_amount=None, name=None):
        self.absorbingMatrix = None
        
        self.group_size = 1
        self._name = name if name else self.__class__.__name__
        self.name = self._name
        self.nStates = 0

        if(loot_amount):
            self.loot_amount = loot_amount
        self._loot_amount = self.loot_amount.copy()


        possible_loot = set(self.loot_odds.keys())
        if(loot_tables is not None):
            for table in loot_tables:
                possible_loot = possible_loot.union(set(table.keys()))

        if(not set(self.loot_amount.keys()).issubset(possible_loot)):
            raise AssertionError

        self.kc = 0
        self.loot_gotten = dict.fromkeys(possible_loot, 0)

        # merge items with the same odds
        self.setNstates()

    def set_groupsize(self, size):
        self.group_size = size

        # prevents python from overwriting the loot amount in other instances of this class as well
        # because it makes total sense that all classes share the same dicts. Thanks python
        self.loot_amount = self._loot_amount.copy()
        for item, amount in self.loot_amount.items():
            self.loot_amount[item] = self.group_size * amount
        self.setNstates()

    def setNstates(self):
        # merge items with the same odds
        try:
            self.nStates = functools.reduce(mul, [amount + 1 for amount in self.loot_amount.values() if amount > 0])
        except Exception as e:
            self.nStates = 0


    def roll_loot(self, table=None):
        if(not table):
            table = self.loot_odds
        roll = random.random()
        for item, odds in table.items():
            if(roll <= odds):
                return [item]
            else:
                roll -= odds

        return []

    def is_completed(self):
        for item, amount in self.loot_amount.items():
            if(self.loot_gotten[item] < amount):
                return False
        return True

    def complete(self):
        self.loot_gotten = dict.fromkeys(self.loot_amount.keys(), 0)
        self.kc = 0
        while not self.is_completed():
            loot = []
            #only check if we actually get something 
            while not loot:
                loot = self.roll_loot()
                self.kc += 1

            #update loot_gotten
            for l in loot:
                #only add loot we're looking for
                if(self.loot_gotten[l] is not None):
                    self.loot_gotten[l] += 1
        
        
        return self.kc, self.loot_gotten

    # we can see state of the drops as an the index to an n dimensional array, so we can use traditional array indexing to calculate the index for the transition matrix and back
    def indexToState(self, index, drops):
        shape = [d + 1 for d in drops.values()]
        state = []
        for dimSize in shape:
            state.append(index % dimSize)
            index //= dimSize
        return state


    def stateToIndex(self, state, drops):
        shape = [d + 1 for d in drops.values()]
        index = 0
        size = 1
        for dimSize, dim in zip(shape, state):
            index += size * dim
            size *= dimSize

        return index

    def contructMatrix(self, nStates, odds, drops):
        data = []
        rowIndex = []
        colIndex = []

        for i in range(0,nStates):
            rowTotal = 0
            for itemIndex, item in enumerate(drops.keys()):
                # skip if the item is not on this loottable

                if(not item in odds):
                    continue
                
                state = self.indexToState(i, drops)
                # if we already enough of this items skip it
                if(state[itemIndex] >= drops[item]):
                    continue

                state[itemIndex] += 1
                j = self.stateToIndex(state, drops)

                rowTotal += odds[item]
                data += [odds[item]]
                rowIndex += [i]
                colIndex += [j]

            # add the diagonal
            data += [1-rowTotal]
            rowIndex += [i]
            colIndex += [i]
        
        data = np.array(data)
        rowIndex = np.array(rowIndex, dtype='int')
        colIndex = np.array(colIndex, dtype='int')
        return coo_matrix((data, (rowIndex, colIndex)), shape=(nStates,nStates)).tocsr()
        

    def convertToMarkovChain(self):
        
        # list all the items we need to get
        try:
            drops = {item: amount for item, amount in self.loot_amount.items() if amount > 0}
        except:
            print(self.loot_amount.items())
            return

        # number of states in matrix * double size / 2 (because the resulting matrix is triangular)
        memUsage = ((self.nStates ** 2 * 64 / 2)/ (1024**2))
        print(f"{self.name} states: {self.nStates}, approx matrix memory usage: {memUsage} MB")
        if(self.nStates > 4096):
            return False

        # generate tables for all loot tables
        m1 = self.contructMatrix(self.nStates, self.loot_odds, drops)
        self.absorbingMatrix = m1
        if(len(self.secondary_odds.keys())):
            m2 = self.contructMatrix(self.nStates, self.secondary_odds, drops)
            self.absorbingMatrix *= m2
        if(len(self.tertiary_odds.keys())):
            m3 = self.contructMatrix(self.nStates, self.tertiary_odds, drops)
            self.absorbingMatrix *= m3
        if(len(self.quaternary_odds.keys())):
            m4 = self.contructMatrix(self.nStates, self.quaternary_odds, drops)
            self.absorbingMatrix *= m4
        
        return True

    def getAbsorbingMatrixGraph(self):


        copy = self.absorbingMatrix.copy()
        self.absorbingMatrix.shape
        (width, _) = copy.shape
        finalState = (0,width - 1)
        y = [float(copy[finalState])]

        copy = self.absorbingMatrix.copy()
        while(copy[finalState] < 0.99999):
            copy *= self.absorbingMatrix
            y += [copy[finalState]]


        x = [i for i in range(1,len(y)+1)]

        # y index is [kc-1] compensate for that
        half = next(i[0] for i in enumerate(y) if i[1] > 0.5) + 1

        # convert to pdf (and percentages)
        pdf = [(j - y[it-1])*100 for it,j in enumerate(y)]
        pdf[0] = self.absorbingMatrix[finalState] * 100

        average = sum(xi * yi/100 for xi, yi in zip(x,pdf))
        mode = pdf.index(max(pdf)) + 1

        # limit the size of the graph
        cutoff = 0.999

        x = [x1 for it, [x1,y1] in enumerate(zip(x,y)) if y1 < cutoff or it == 0]
        pdf = [pdf for it, [pdf,y1] in enumerate(zip(pdf,y)) if y1 < cutoff or it == 0]
        # convert to percentages here as well
        y = [y1 * 100 for it, y1 in enumerate(y) if y1 < cutoff or it == 0]

        
        closeCutoff = next(i[0] for i in enumerate(y) if i[1] > max(pdf)/100) + 1
        # remove early nodes if the cutoff isn't close to the start of the graph
        if(closeCutoff > len(y) / 10):
            x = x[closeCutoff:]
            pdf = pdf[closeCutoff:]
            y = y[closeCutoff:]
        else:
            closeCutoff = 0


        return x, y, pdf, mode, half, average, closeCutoff


#slayer bosses
class grotesque_guardians(monster):
    loot_odds = {"granite gloves":1/500, "granite ring":1/500, "granite hamnmer":1/750, "black tourmaline core":1/1000}
    secondary_odds = {"granite gloves":1/500, "granite ring":1/500, "granite hamnmer":1/750, "black tourmaline core":1/1000}
    loot_amount = {"granite gloves":1, "granite ring":1, "granite hamnmer":1, "black tourmaline core":1}

    def roll_loot(self):
        #2 rolls on the table each kill
        return super().roll_loot() + super().roll_loot()


class abyssal_sire(monster):
    loot_odds = {"bludgeon piece":62/12800, "abyssal dagger":26/12800}
    loot_amount = {"bludgeon piece":3, "abyssal dagger":0}

class cave_kraken(monster):
    loot_odds = {"trident of the seas (full)":1/512, "kraken tentacle":1/400}
    loot_amount = {"trident of the seas (full)":1,"kraken tentacle":1}

class cerberus(monster):
    loot_odds = {"primordial crystal":1/512, "pegasian_crystal":1/512, "eternal crystal":1/512, "smouldering stone":1/512}
    loot_amount = {"primordial crystal":1,"pegasian_crystal":1,"eternal crystal":1,"smouldering stone":0}

class thermonuclear_smoke_devil(monster):
    loot_odds = {"occult necklace":1/350, "smoke battlestaff":1/512}
    loot_amount = {"occult necklace":0,"smoke battlestaff":1}

class alchemical_hydra(monster):
    loot_odds = {"ring piece":1/181.067098222,"hydra tail":1/513.025409666, "hydra leather":1/514.029373286,"hydra's claw":1/1001.0007505,"dragon thrownaxe":1/2000, "dragon knife":1/2001.0005}
    loot_amount = {"ring piece":0,"hydra tail":1,"hydra leather":1,"hydra's claw":1,"dragon thrownaxe":0,"dragon knife":0}

class chaos_fanatic(monster):
    loot_odds = {"odium shard 1":1/256, "malediction shard 1":1/256}
    loot_amount = {"odium shard 1":1,"malediction shard 1":1}

class crazy_archaeologist(monster):
    loot_odds = {"odium shard 2":1/256, "malediction shard 2":1/256, "fedora":1/128}
    loot_amount = {"odium shard 2":1,"malediction shard 2":1,"fedora":1}

class scorpia(monster):
    loot_odds = {"odium shard 3":1/256, "malediction shard 3":1/256}
    loot_amount = {"odium shard 3":1,"malediction shard 3":1}

class vetion(monster):
    loot_odds = {"ring of the gods":1/512, "dragon pickaxe":0.75/128, "dragon 2h sword":0.5/128}
    loot_amount = {"ring of the gods":1,"dragon pickaxe":0,"dragon 2h sword":0}

class venenatis(monster):
    loot_odds = {"treasonous ring":1/512, "dragon pickaxe":0.75/128, "dragon 2h sword":0.5/128}
    loot_amount = {"treasonous ring":1,"dragon pickaxe":0,"dragon 2h sword":0}

class callisto(monster):
    loot_odds = {"tyrannical ring":1/512, "dragon pickaxe":0.75/128, "dragon 2h sword":0.5/128}
    loot_amount = {"tyrannical ring":1,"dragon pickaxe":0,"dragon 2h sword":0}

class obor(monster):
    loot_odds = {"hill giant club":1/118}
    loot_amount = {"hill giant club":1}

class bryophyta(monster):
    loot_odds = {"bryophyta's essence":1/118}
    loot_amount = {"bryophyta's essence":1}

class king_black_dragon(monster):
    loot_odds = {"dragon pickaxe":1/1500, "draconic visage":1/5000}
    loot_amount = {"dragon pickaxe":0, "draconic visage":0}

class mimic(monster):
    loot_odds = {"3rd age ring":1/40}
    loot_amount = {"3rd age ring":1}

class hespori(monster):
    loot_odds = {"bottemless bucket":1/35, "white lilly seed":1/16}
    secondary_odds = {"attas seed": 1/3, "kronos seed":1/3, "iasor seed":1/3}
    loot_amount = {"bottemless bucket":1, "white lilly seed":1, "attas seed":1, "kronos seed":1, "iasor seed":1}

    def __init__(self, **kwargs):
        kwargs["loot_tables"] = [self.secondary_odds]
        super().__init__(**kwargs)

    def roll_loot(self):
        return super().roll_loot() + super().roll_loot(self.secondary_odds)

class zalcano(monster):
    #zalcano shard odds scale lineair with points
    #https://twitter.com/JagexEd/status/1259855680795742226
    # were assuming 200 contribution points out of 1000, change ratio if needed
    contribution_points = 200
    total_points = 1000

    shard_odds = (1 / 1500 + (1 / 750 - 1 / 1500) * contribution_points / total_points)
    loot_odds = {"crystal tool seed":1/(200 * total_points / contribution_points), "zalcano shard":shard_odds}
    loot_amount = {"crystal tool seed":1, "zalcano shard":1}
    zalcano_shard = {"max_odds":1/750, "min_odds":1/1500}

class wintertodt(monster):
    loot_odds = {"pyromancer outfit":1/150,"bruma torch":1/150,"warm gloves":1/150,"tome of fire":1/1000,"dragon axe":1/10000}
    loot_amount = {"pyromancer outfit":4,"bruma torch":1,"warm gloves":1,"tome of fire":1, "dragon axe":0}
    kc_name = 'loot rolls'
        
class tempoross(monster):
    loot_odds = {"soaked page":100/5369, "fish barrel":1/400, "tackle box":1/400, "big harpoonfish":1/1600, "Tome of water":1/1600, "dragon harpoon":1/8000}
    loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":0, "Tome of water":1, "dragon harpoon":0}
    kc_name = 'loot rolls'

class guardians_of_the_rift(monster):
    loot_odds = {"catalytic talisman":1/200, "abyssal needle":1/300, "abyssal lantern":1/700, "tarnished locket":1/1250, "lost bag": 1/1750, "Abyssal green dye": 1/1200, "Abyssal blue dye": 1/1200, "Abyssal red dye": 1/1200}
    loot_amount = {"catalytic talisman":1, "abyssal needle":1, "abyssal lantern":1, "tarnished locket":1, "lost bag": 0, "Abyssal green dye": 0, "Abyssal blue dye": 0, "Abyssal red dye": 0}
    kc_name = 'loot rolls'

class corrupted_gauntlet(monster):
    loot_odds = {"enhanced crystal weapon seed":1/400, "crystal armour seed":1/50}
    loot_amount = {"enhanced crystal weapon seed":1,"crystal armour seed":1}

class gauntlet(monster):
    loot_odds = {"enhanced crystal weapon seed":1/2000, "crystal armour seed":1/50}
    loot_amount = {"enhanced crystal weapon seed":1,"crystal armour seed":1}

class dagannoth_rex(monster):
    loot_odds = {"berserker ring":1/128, "warrior ring": 1/128, "dragon axe": 1/128}
    loot_amount = {"berserker ring":1,"warrior ring":1,"dragon axe":0}

class dagannoth_supreme(monster):
    loot_odds = {"archer ring": 1/128, "seercul":1/128, "dragon axe":1/128}
    loot_amount = {"archer ring":1,"seercul":1,"dragon axe":0}

class dagannoth_prime(monster):
    loot_odds = {"seers ring":1/128, "mud battlestaff":1/128, "dragon axe":1/128}
    loot_amount = {"seers ring":1,"mud battlestaff":1,"dragon axe":0}

class dkings(monster):
    loot_odds = {"seers ring":1/128, "mud battlestaff":1/128, "dragon axe":1/128}
    secondary_odds = {"archer ring": 1/128, "seercul":1/128, "dragon axe":1/128}
    tertiary_odds = {"berserker ring":1/128, "warrior ring": 1/128, "dragon axe": 1/128}
    loot_amount = {"berserker ring":1,"warrior ring":1,"archer ring":1,"seercul":1,"seers ring":1,"mud battlestaff":1,"dragon axe":1}

    def __init__(self, **kwargs):
        kwargs["loot_tables"] = [self.secondary_odds, self.tertiary_odds]
        super().__init__(**kwargs)

    def roll_loot(self):
        return super().roll_loot() + super().roll_loot(self.secondary_odds) + super().roll_loot(self.tertiary_odds)

class sarachnis(monster):
    loot_odds = {"sarachnis cudgel":1/384, "egg sac":1/20}
    loot_amount = {"sarachnis cudgel":1,"egg sac":1}

class kalphite_queen(monster):
    loot_odds = {"dragon chain":1/128, "dragon 2h sword":1/256}
    loot_amount = {"dragon chain":0,"dragon 2h sword":0}

class zulrah(monster):
    loot_odds = {"tanzanite fang":1/1024, "magic fang":1/1024, "serpentine visage":1/1024, "uncut onyx":1/1024, "magma mutagen":1/13106, "tanzanite mutagen":1/13106}
    secondary_odds = {"tanzanite fang":1/1024, "magic fang":1/1024, "serpentine visage":1/1024, "uncut onyx":1/1024, "magma mutagen":1/13106, "tanzanite mutagen":1/13106}
    loot_amount = {"tanzanite fang":1,"magic fang":1,"serpentine visage":1,"uncut onyx":0, "magma mutagen":0, "tanzanite mutagen":0}

    def roll_loot(self):
        #2 rolls on the table each kill
        return super().roll_loot() + super().roll_loot()

class vorkath(monster):
    loot_odds = {"dragonbone necklace":1/1000}
    secondary_odds = {"draconic visage":1/5000}
    tertiary_odds = {"skeletal visage":1/5000}
    loot_amount = {"dragonbone necklace":1,"skeletal visage":1,"draconic visage":0}
    
    def __init__(self, **kwargs):
        kwargs["loot_tables"] = [self.secondary_odds, self.tertiary_odds]
        super().__init__(**kwargs)

class corporeal_beast(monster):
    loot_odds = {"arcane sigil":1/1365,"spectral sigil":1/1365,"elysian sigil":1/4095,"spirit shield":8/512,"holy elixer":3/512}
    loot_amount = {"arcane sigil":1,"spectral sigil":1,"elysian sigil":1,"spirit shield":1,"holy elixer":1}

class gwd(monster):
    minion_loot = {}

    def roll_loot(self):
        loot = super().roll_loot()
        for _ in range(3):
            loot += super().roll_loot(self.minion_loot)

        return loot

class commander_zilyana(gwd):
    secondary_odds = {"saradomin sword":3/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    tertiary_odds = {"saradomin sword":3/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    quaternary_odds = {"saradomin sword":3/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    loot_odds = {"saradomin sword":1/127,"saradoming's light":1/254, "armadyl crossbow":1/508, "saradomin hilt":1/508,"godsword shard 1":1/762,"godsword shard 2":1/762,"godsword shard 3":1/762}
    loot_amount = {"saradomin sword":1,"saradoming's light":1, "armadyl crossbow":1, "saradomin hilt":1,"godsword shard 1":0,"godsword shard 2":0,"godsword shard 3":0}

class general_graardor(gwd):
    secondary_odds = {"bandos boots":1/16129,"bandos tassets":1/16129,"bandos chestplate":1/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    tertiary_odds = {"bandos boots":1/16129,"bandos tassets":1/16129,"bandos chestplate":1/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    quaternary_odds = {"bandos boots":1/16129,"bandos tassets":1/16129,"bandos chestplate":1/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    loot_odds = {"bandos chestplate":1/381,"bandos tassets":1/381, "bandos boots":1/381, "bandos hilt":1/508,"godsword shard 1":1/762,"godsword shard 2":1/762,"godsword shard 3":1/762}
    loot_amount = {"bandos chestplate":1,"bandos tassets":1, "bandos boots":1, "bandos hilt":1,"godsword shard 1":0,"godsword shard 2":0,"godsword shard 3":0}

class kril_tsutsaroth(gwd):
    secondary_odds = {"zamorak spear":3/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    tertiary_odds = {"zamorak spear":3/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    quaternary_odds = {"zamorak spear":3/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    loot_odds = {"zamorak spear":1/127,"steam battlestaff":1/127, "staff of the dead":1/508, "zamorak hilt":1/508,"godsword shard 1":1/762,"godsword shard 2":1/762,"godsword shard 3":1/762}
    loot_amount = {"zamorak spear":1,"steam battlestaff":1, "staff of the dead":1, "zamorak hilt":1,"godsword shard 1":0,"godsword shard 2":0,"godsword shard 3":0}

class kree_arra(gwd):
    secondary_odds = {"armadyl helmet":1/16129,"armadyl chestplate":1/16129,"armadyl chainskirt":1/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    tertiary_odds = {"armadyl helmet":1/16129,"armadyl chestplate":1/16129,"armadyl chainskirt":1/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    quaternary_odds = {"armadyl helmet":1/16129,"armadyl chestplate":1/16129,"armadyl chainskirt":1/16129,"godsword shard 1":1/1524,"godsword shard 2":1/1524,"godsword shard 3":1/1524}
    loot_odds = {"armadyl helmet":1/381,"armadyl chestplate":1/381, "armadyl chainskirt":1/381, "armadyl hilt":1/508,"godsword shard 1":1/762,"godsword shard 2":1/762,"godsword shard 3":1/762}
    loot_amount = {"armadyl helmet":1,"armadyl chestplate":1, "armadyl chainskirt":1, "armadyl hilt":1,"godsword shard 1":0,"godsword shard 2":0,"godsword shard 3":0}

class nightmare(monster):
    loot_odds = {"inquisitor's great helm":1/600,"inquisitor's hauberk":1/600,"inquisitor's plateskirt":1/600, "inquisitor's mace":1/1200, "nightmare staff":1/400}
    secondary_odds = {"eldritch orb":1/1800, "harmonised orb":1/1800,"volatile orb":1/1800}
    loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":1, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}

    def __init__(self, teamsize=1, **kwargs):
        kwargs["loot_tables"] = [self.secondary_odds]
        super().__init__(**kwargs)
        self.teamsize = teamsize

    def roll_loot(self):
        team_loot = super().roll_loot() + super().roll_loot(self.secondary_odds)
        
        if (random.random() < (self.teamsize-5)/100):
            team_loot += super().roll_loot()

        if (random.random() < (self.teamsize-5)/100):
            super().roll_loot(self.secondary_odds)

        loot = []
        for l in team_loot:
            if(random.random() < 1/self.teamsize):
                loot += [l]

        return loot

class phosanis_nightmare(monster):
    loot_odds = {"inquisitor's great helm":1/1000,"inquisitor's hauberk":1/1000,"inquisitor's plateskirt":1/1000, "inquisitor's mace":1/2000, "nightmare staff":1/667}
    secondary_odds = {"eldritch orb":1/3000, "harmonised orb":1/3000,"volatile orb":1/3000}
    loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":1, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}
    
    def __init__(self, teamsize=1, **kwargs):
        kwargs["loot_tables"] = [self.secondary_odds]
        super().__init__(**kwargs)
        self.teamsize = teamsize

class nex(monster):
    loot_odds = {"Zaryte vambraces":1/172,"Torva full helm (damaged)":1/258,"Torva platebody (damaged)":1/258, "Torva platelegs (damaged)":1/258, "Nihil horn":1/258, "Ancient hilt":1/516}
    loot_amount = {"Zaryte vambraces":1,"Torva full helm (damaged)":1,"Torva platebody (damaged)":1, "Torva platelegs (damaged)":1, "Nihil horn":1, "Ancient hilt":1}


    def __init__(self, teamsize=1, **kwargs):
        self.loot_odds = self.loot_odds.copy()
        for drop in self.loot_odds:
            self.loot_odds[drop] /= teamsize
        super().__init__(**kwargs)
        self.teamsize = teamsize

class barrows(monster):
    loot_odds = {"dharock's greataxe":1/2448,"dharock's helm":1/2448,"dharock's platelegs":1/2448,"dharock's platebody":1/2448,
    "ahrims's hood":1/2448,"ahrims's robetop":1/2448,"ahrim's robeskirt":1/2448,"ahrim's staff":1/2448,
    "karil's hood":1/2448,"karil's leathertop":1/2448,"karil's leatherskirt":1/2448,"karil's crossbow":1/2448,
    "torag's helm":1/2448,"torags's platebody":1/2448,"torags's platelegs":1/2448,"torag's hammers":1/2448,
    "veracs's helm":1/2448,"veracs's brassard":1/2448,"veracs's plateskirt":1/2448,"veracs's flail":1/2448,
    "guthan's helm":1/2448,"guthans's platebody":1/2448,"guthans's chainskirt":1/2448,"guthans's spear":1/2448}
    
    loot_amount = {"dharock's greataxe":1,"dharock's helm":1,"dharock's platelegs":1,"dharock's platebody":1,
    "ahrims's hood":1,"ahrims's robetop":1,"ahrim's robeskirt":1,"ahrim's staff":1,
    "karil's hood":1,"karil's leathertop":1,"karil's leatherskirt":1,"karil's crossbow":1,
    "torag's helm":1,"torags's platebody":1,"torags's platelegs":1,"torag's hammers":1,
    "veracs's helm":1,"veracs's brassard":1,"veracs's plateskirt":1,"veracs's flail":1,
    "guthan's helm":1,"guthans's platebody":1,"guthans's chainskirt":1,"guthans's spear":1}

    equipment_odds = 1/102

    for drop in loot_odds:
        loot_odds[drop] *= 7


    def roll_loot(self):
        loot = []
        for _ in range(7):
            l = []
            if(random.random() <= self.equipment_odds):
                l = random.choice(list(self.loot_odds.keys()))
                #can't get the same item multiple times in the same chest but the odds of getting any item remain the same
                while l in loot:
                    l = random.choice(list(self.loot_odds.keys()))
                loot += [l]

        return loot

    def convertToMarkovChain(self):
        self.absorbingMatrix = self.constructMatrix()
        return self.group_size == 1

    def constructMatrix(self):
        # barrows has too many items, since they all have the same odds we can model them with an index of how many items we have. 
        self.nStates = 25
        data = []
        rowIndex = []
        colIndex = []
        for i in range(0,self.nStates):
            rowTotal = 0

            for j in range(1, min(8, self.nStates - i)):
                odds = self.itemOdds(i, j)
                data += [odds]
                rowTotal += odds
                rowIndex += [i]
                colIndex += [i + j]

            # add the diagonal
            data += [1-rowTotal]
            rowIndex += [i]
            colIndex += [i]
        
        data = np.array(data)
        rowIndex = np.array(rowIndex, dtype='int')
        colIndex = np.array(colIndex, dtype='int')
        return coo_matrix((data, (rowIndex, colIndex)), shape=(self.nStates,self.nStates)).tocsr()

    def itemOdds(self, gotten, new):
        odds = 0

        for i in range(new,8):
            odds += math.comb(7,i) * (1/102)**i * (101/102)**(7-i) * math.comb(i, new) * reduce(mul, [((24 - gotten - j) / (24 - j)) for j in range(new)], 1) * reduce(mul, [(1 - (24 - new - gotten - j) / (24 - new - j)) for j in range(i - new)], 1)
        return odds


class easy_clues(monster):
    # Group items by their rarity this drastically reduces the amount of nodes in our markov chain to around 1.5 million!
    # Which means that we only need 1,125,000,000,000 doubles worth of memory to hold the transition graph in memory
    # Contact me if you know someone with a supercomputer that wants to run some unoptimized code on it to find out 
    # the exact kc it takes to complete easy clues until Jagex updates the loot table again!
    # Then calculate the odds of getting a new item of the same rarity
    loot_odds = {"Amulet of magic (t)": 1/360, "Wooden shield (g)": 1/1404, "Black full helm (t)": 1/1404, "Black platebody (t)": 1/1404, "Black platelegs (t)": 1/1404, "Black plateskirt (t)": 1/1404, "Black kiteshield (t)": 1/1404, "Black full helm (g)": 1/1404, "Black platebody (g)": 1/1404, "Black platelegs (g)": 1/1404, "Black plateskirt (g)": 1/1404, "Black kiteshield (g)": 1/1404, "Black shield (h1)": 1/1404, "Black shield (h2)": 1/1404, "Black shield (h3)": 1/1404, "Black shield (h4)": 1/1404, "Black shield (h5)": 1/1404, "Black helm (h1)": 1/1404, "Black helm (h2)": 1/1404, "Black helm (h3)": 1/1404, "Black helm (h4)": 1/1404, "Black helm (h5)": 1/1404, "Black platebody (h1)": 1/1404, "Black platebody (h2)": 1/1404, "Black platebody (h3)": 1/1404, "Black platebody (h4)": 1/1404, "Black platebody (h5)": 1/1404, "Steel full helm (t)": 1/1404, "Steel platebody (t)": 1/1404, "Steel platelegs (t)": 1/1404, "Steel plateskirt (t)": 1/1404, "Steel kiteshield (t)": 1/1404, "Steel full helm (g)": 1/1404, "Steel platebody (g)": 1/1404, "Steel platelegs (g)": 1/1404, "Steel plateskirt (g)": 1/1404, "Steel kiteshield (g)": 1/1404, "Iron full helm (t)": 1/1404, "Iron platebody (t)": 1/1404, "Iron platelegs (t)": 1/1404, "Iron plateskirt (t)": 1/1404, "Iron kiteshield (t)": 1/1404, "Iron full helm (g)": 1/1404, "Iron platebody (g)": 1/1404, "Iron platelegs (g)": 1/1404, "Iron plateskirt (g)": 1/1404, "Iron kiteshield (g)": 1/1404, "Bronze full helm (t)": 1/1404, "Bronze platebody (t)": 1/1404, "Bronze platelegs (t)": 1/1404, "Bronze plateskirt (t)": 1/1404, "Bronze kiteshield (t)": 1/1404, "Bronze full helm (g)": 1/1404, "Bronze platebody (g)": 1/1404, "Bronze platelegs (g)": 1/1404, "Bronze plateskirt (g)": 1/1404, "Bronze kiteshield (g)": 1/1404, "Studded body (g)": 1/1404, "Studded chaps (g)": 1/1404, "Studded body (t)": 1/1404, "Studded chaps (t)": 1/1404, "Leather body (g)": 1/1404, "Leather chaps (g)": 1/1404, "Blue wizard hat (g)": 1/1404, "Blue wizard robe (g)": 1/1404, "Blue skirt (g)": 1/1404, "Blue wizard hat (t)": 1/1404, "Blue wizard robe (t)": 1/1404, "Blue skirt (t)": 1/1404, "Black wizard hat (g)": 1/1404, "Black wizard robe (g)": 1/1404, "Black skirt (g)": 1/1404, "Black wizard hat (t)": 1/1404, "Black wizard robe (t)": 1/1404, "Black skirt (t)": 1/1404, "Saradomin robe top": 1/1404, "Saradomin robe legs": 1/1404, "Guthix robe top": 1/1404, "Guthix robe legs": 1/1404, "Zamorak robe top": 1/1404, "Zamorak robe legs": 1/1404, "Ancient robe top": 1/1404, "Ancient robe legs": 1/1404, "Armadyl robe top": 1/1404, "Armadyl robe legs": 1/1404, "Bandos robe top": 1/1404, "Bandos robe legs": 1/1404, "Bob's red shirt": 1/1404, "Bob's green shirt": 1/1404, "Bob's blue shirt": 1/1404, "Bob's black shirt": 1/1404, "Bob's purple shirt": 1/1404, "Highwayman mask": 1/1404, "Blue beret": 1/1404, "Black beret": 1/1404, "Red beret": 1/1404, "White beret": 1/1404, "A powdered wig": 1/1404, "Beanie": 1/1404, "Imp mask": 1/1404, "Goblin mask": 1/1404, "Sleeping cap": 1/1404, "Flared trousers": 1/1404, "Pantaloons": 1/1404, "Black cane": 1/1404, "Staff of bob the cat": 1/1404, "Amulet of power (t)": 1/1404, "Ham joint": 1/1404, "Rain bow": 1/1404, "Golden chef's hat": 1/2808, "Golden apron": 1/2808, "Red elegant shirt": 1/2808, "Red elegant blouse": 1/2808, "Red elegant legs": 1/2808, "Red elegant skirt": 1/2808, "Green elegant shirt": 1/2808, "Green elegant blouse": 1/2808, "Green elegant legs": 1/2808, "Green elegant skirt": 1/2808, "Blue elegant shirt": 1/2808, "Blue elegant blouse": 1/2808, "Blue elegant legs": 1/2808, "Blue elegant skirt": 1/2808, "Team cape zero": 1/5616, "Team cape i": 1/5616, "Team cape x": 1/5616, "Cape of skulls": 1/5616, "Monk's robe top (g)": 1/14040, "Monk's robe (g)": 1/14040,  }
    
    loot_amount = {"Amulet of magic (t)": 1, "Wooden shield (g)": 1, "Black full helm (t)": 1, "Black platebody (t)": 1, "Black platelegs (t)": 1, "Black plateskirt (t)": 1, "Black kiteshield (t)": 1, "Black full helm (g)": 1, "Black platebody (g)": 1, "Black platelegs (g)": 1, "Black plateskirt (g)": 1, "Black kiteshield (g)": 1, "Black shield (h1)": 1, "Black shield (h2)": 1, "Black shield (h3)": 1, "Black shield (h4)": 1, "Black shield (h5)": 1, "Black helm (h1)": 1, "Black helm (h2)": 1, "Black helm (h3)": 1, "Black helm (h4)": 1, "Black helm (h5)": 1, "Black platebody (h1)": 1, "Black platebody (h2)": 1, "Black platebody (h3)": 1, "Black platebody (h4)": 1, "Black platebody (h5)": 1, "Steel full helm (t)": 1, "Steel platebody (t)": 1, "Steel platelegs (t)": 1, "Steel plateskirt (t)": 1, "Steel kiteshield (t)": 1, "Steel full helm (g)": 1, "Steel platebody (g)": 1, "Steel platelegs (g)": 1, "Steel plateskirt (g)": 1, "Steel kiteshield (g)": 1, "Iron full helm (t)": 1, "Iron platebody (t)": 1, "Iron platelegs (t)": 1, "Iron plateskirt (t)": 1, "Iron kiteshield (t)": 1, "Iron full helm (g)": 1, "Iron platebody (g)": 1, "Iron platelegs (g)": 1, "Iron plateskirt (g)": 1, "Iron kiteshield (g)": 1, "Bronze full helm (t)": 1, "Bronze platebody (t)": 1, "Bronze platelegs (t)": 1, "Bronze plateskirt (t)": 1, "Bronze kiteshield (t)": 1, "Bronze full helm (g)": 1, "Bronze platebody (g)": 1, "Bronze platelegs (g)": 1, "Bronze plateskirt (g)": 1, "Bronze kiteshield (g)": 1, "Studded body (g)": 1, "Studded chaps (g)": 1, "Studded body (t)": 1, "Studded chaps (t)": 1, "Leather body (g)": 1, "Leather chaps (g)": 1, "Blue wizard hat (g)": 1, "Blue wizard robe (g)": 1, "Blue skirt (g)": 1, "Blue wizard hat (t)": 1, "Blue wizard robe (t)": 1, "Blue skirt (t)": 1, "Black wizard hat (g)": 1, "Black wizard robe (g)": 1, "Black skirt (g)": 1, "Black wizard hat (t)": 1, "Black wizard robe (t)": 1, "Black skirt (t)": 1, "Saradomin robe top": 1, "Saradomin robe legs": 1, "Guthix robe top": 1, "Guthix robe legs": 1, "Zamorak robe top": 1, "Zamorak robe legs": 1, "Ancient robe top": 1, "Ancient robe legs": 1, "Armadyl robe top": 1, "Armadyl robe legs": 1, "Bandos robe top": 1, "Bandos robe legs": 1, "Bob's red shirt": 1, "Bob's green shirt": 1, "Bob's blue shirt": 1, "Bob's black shirt": 1, "Bob's purple shirt": 1, "Highwayman mask": 1, "Blue beret": 1, "Black beret": 1, "Red beret": 1, "White beret": 1, "A powdered wig": 1, "Beanie": 1, "Imp mask": 1, "Goblin mask": 1, "Sleeping cap": 1, "Flared trousers": 1, "Pantaloons": 1, "Black cane": 1, "Staff of bob the cat": 1, "Amulet of power (t)": 1, "Ham joint": 1, "Rain bow": 1, "Golden chef's hat": 1, "Golden apron": 1, "Red elegant shirt": 1, "Red elegant blouse": 1, "Red elegant legs": 1, "Red elegant skirt": 1, "Green elegant shirt": 1, "Green elegant blouse": 1, "Green elegant legs": 1, "Green elegant skirt": 1, "Blue elegant shirt": 1, "Blue elegant blouse": 1, "Blue elegant legs": 1, "Blue elegant skirt": 1, "Team cape zero": 1, "Team cape i": 1, "Team cape x": 1, "Cape of skulls": 1, "Monk's robe top (g)": 1, "Monk's robe (g)": 1,  }

    loot_rolls = 3

    def roll_loot(self):
        loot = []
        for _ in range(self.loot_rolls):
            l = random.choice(list(self.loot_odds.keys()))
            loot += [l]

        return loot

    def convertToTotals(self):
        self.loot_totals = {}
        
        for _, v in self.loot_odds.items():
            self.loot_totals[v] = 1 if v not in self.loot_totals.keys() else self.loot_totals[v] + 1

        print(self.loot_totals)

    def convertToMarkovChain(self):
        self.convertToTotals()
        self.absorbingMatrix = self.constructMatrix()
        return self.group_size == 1

    def constructMatrix(self):
        self.nStates = 2 ** len(self.loot_totals.keys()) * reduce(mul, [t + 1 for t in self.loot_totals.values()])
        data = []
        rowIndex = []
        colIndex = []
        for i in range(0,self.nStates):
            rowTotal = 0

            for lootIndex, (odds, total) in enumerate(self.loot_totals.items()):
                state = self.indexToState(i, self.loot_totals)
                
                # if we already enough of this item group skip it
                if(state[lootIndex] >= total):
                    continue
                
                odds = self.itemOdds(odds, state[lootIndex], total)
                
                state[lootIndex] += 1
                j = self.stateToIndex(state, self.loot_totals)
                
                data += [odds]
                rowTotal += odds
                rowIndex += [i]
                colIndex += [j]

            # add the diagonal
            data += [1-rowTotal]
            rowIndex += [i]
            colIndex += [i]
        
        data = np.array(data)
        rowIndex = np.array(rowIndex, dtype='int')
        colIndex = np.array(colIndex, dtype='int')
        return coo_matrix((data, (rowIndex, colIndex)), shape=(self.nStates,self.nStates)).tocsr()

    def itemOdds(self, baseOdds, current, total):
        # Return the odds of getting a new item of the same rarity 
        return baseOdds * total / current


class theatre_of_blood(monster):
    #https://twitter.com/JagexKieren/status/1145376451446751232/photo/1
    base_odds = 1/9.1

    loot_odds = {"scythe of vitur":1/19, "grazi rapier":2/19,"sanguinesti staff":2/19, "justiciar faceguard":2/19, "justiciar chestguard":2/19, "justiciar legguard":2/19, "avernic hilt":8/19}

    loot_amount = {"scythe of vitur":1, "grazi rapier":1,"sanguinesti staff":1, "justiciar faceguard":1, "justiciar chestguard":1, "justiciar legguard":1, "avernic hilt":1}

    def __init__(self, teamsize=1, **kwargs):
        self.loot_odds = self.loot_odds.copy()
        for drop in self.loot_odds:
            self.loot_odds[drop] *= (self.base_odds / teamsize)
        super().__init__(**kwargs)
        self.teamsize = teamsize


class theatre_of_blood_hard_mode(monster):
    # https://twitter.com/JagexArcane/status/1485992982906085376
    base_odds = 13/100

    loot_odds = {"scythe of vitur":1/18, "grazi rapier":2/18,"sanguinesti staff":2/18, "justiciar faceguard":2/18, "justiciar chestguard":2/18, "justiciar legguard":2/18, "avernic hilt":7/18}
    
    secondary_odds = {"Sanguine dust":1/275, "Sanguine ornament kit":1/150,"holy ornament kit":1/100}

    loot_amount = {"scythe of vitur":1, "grazi rapier":1,"sanguinesti staff":1, "justiciar faceguard":1, "justiciar chestguard":1, "justiciar legguard":1, "avernic hilt":1, "Sanguine dust":0, "Sanguine ornament kit":0,"holy ornament kit":0}

    def __init__(self, teamsize=1, **kwargs):
        self.loot_odds = self.loot_odds.copy()
        kwargs["loot_tables"] = [self.secondary_odds]
        for drop in self.loot_odds:
            self.loot_odds[drop] *= (self.base_odds / teamsize)
        super().__init__(**kwargs)
        self.teamsize = teamsize


class chambers_of_xeric(monster):
    team_points = 31000
    personal_points = 31000

    unique_loot_point_cap = 570000
    unique_loot_odds_at_cap = 0.657
    # this doesn't deal properly with points over the point cap
    odds_adjustment = min(team_points, unique_loot_point_cap)/unique_loot_point_cap * unique_loot_odds_at_cap * personal_points/team_points

    loot_odds = {"dexterous prayer scroll":20/69,"arcane prayer scroll":20/69,"twisted buckler":4/69,"dragon hunter crossbow":4/69,"dinh's bulwark":3/69,"ancestral hat":3/69,"ancestral robe top":3/69,"ancestral robe bottom":3/69, "dragon claws":3/69,"elder maul":2/69,"kodai insignia":2/69,"twisted bow":2/69}
    for drop in loot_odds:
        loot_odds[drop] *= odds_adjustment
    loot_amount = {"dexterous prayer scroll":1,"arcane prayer scroll":1,"twisted buckler":1,"dragon hunter crossbow":1,"dinh's bulwark":1,"ancestral hat":1,"ancestral robe top":1,"ancestral robe bottom":1, "dragon claws":1,"elder maul":1,"kodai insignia":1,"twisted bow":1}


class chaos_elemental(monster):
    loot_odds = {"Dragon pickaxe":1/256,"Dragon 2h sword":20/69}
    loot_amount = {"Dragon pickaxe":0, "Dragon 2h sword":0}


def optionalBosses():
    hydra = alchemical_hydra(loot_amount={"ring piece":3,"hydra tail":1,"hydra leather":1,"hydra's claw":1,"dragon thrownaxe":0,"dragon knife":0}, name="Alchemical Hydra + brimstone ring")
    hydra2 = alchemical_hydra(loot_amount={"ring piece":3,"hydra tail":1,"hydra leather":1,"hydra's claw":1,"dragon thrownaxe":1,"dragon knife":1}, name="Alchemical Hydra + brimstone ring + knives&axes")
    krak = cave_kraken(loot_amount={"kraken tentacle":11, "trident of the seas (full)":1}, name="Cave Kraken + 11 tents")
    kq = kalphite_queen(loot_amount={"dragon chain":1,"dragon 2h sword":1}, name= "Kalphite Queen chain+2h")
    ce = chaos_elemental(loot_amount = {"Dragon pickaxe":1, "Dragon 2h sword":0}, name="Chaos Elemental dpick")
    kbd = king_black_dragon(loot_amount={"dragon pickaxe":1, "draconic visage":1/5000}, name="King Black Dragon, visage + pick")
    ven = venenatis(loot_amount={"treasonous ring":1,"dragon pickaxe":1,"dragon 2h sword":1}, name="Wildy boss, ring + pick + 2h")
    ven2 = venenatis(loot_amount={"treasonous ring":1,"dragon pickaxe":1,"dragon 2h sword":0}, name="Wildy boss, ring + pick")
    ven3 = venenatis(loot_amount={"treasonous ring":0,"dragon pickaxe":1,"dragon 2h sword":0}, name="Wildy boss just the d pick")
    cerb = cerberus(loot_amount = {"primordial crystal":1,"pegasian_crystal":1,"eternal crystal":1,"smouldering stone":1}, name="Cerberus + 1 smouldering")
    cerb2 = cerberus(loot_amount = {"primordial crystal":1,"pegasian_crystal":1,"eternal crystal":1,"smouldering stone":3}, name= "Cerberus + 3 smouldering")
    sire = abyssal_sire(loot_amount = {"bludgeon piece":3, "abyssal dagger":1}, name= "Abyssal Sire + dagger")
    dks = dkings(name="Dagannoth Kings")
    corp = corporeal_beast(loot_amount = {"arcane sigil":1,"spectral sigil":1,"elysian sigil":1,"spirit shield":3,"holy elixer":3}, name = "Corporeal Beast + 3 blessed shields")
    zul = zulrah(loot_amount = {"tanzanite fang":1,"magic fang":1,"serpentine visage":1,"uncut onyx":1, "magma mutagen":1, "tanzanite mutagen":1}, name="Zulrah + onyx + mutagens")
    zul2 = zulrah(loot_amount = {"tanzanite fang":1,"magic fang":2,"serpentine visage":1,"uncut onyx":0, "magma mutagen":0, "tanzanite mutagen":0}, name="Zulrah, 2 magic fangs")
    night = nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":3, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}, name="Nightmare 3 staves")
    pnight = phosanis_nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":3, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}, name="Phosanis nightmare, 3 staves")
    pnightinq = phosanis_nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":0, "eldritch orb":0, "harmonised orb":0,"volatile orb":0}, name="Phosanis nightmare, full inq + mace")
    pnightjustinq = phosanis_nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":0, "nightmare staff":0, "eldritch orb":0, "harmonised orb":0,"volatile orb":0}, name="Phosanis nightmare, full inq, no mace")
    vork = vorkath(loot_amount = {"dragonbone necklace":1,"skeletal visage":1,"draconic visage":1}, name="Vorkath, both visages")
    cg = corrupted_gauntlet(loot_amount={"enhanced crystal weapon seed":2, "crystal armour seed":6}, name="Corrupted gauntlet, 2 enhanced weapon seeds, 6 armour crystals")
    cg1seed = corrupted_gauntlet(loot_amount={"enhanced crystal weapon seed":1, "crystal armour seed":6}, name="Corrupted gauntlet, 1 enhanced weapon seeds, 6 armour crystals")

    temp = tempoross(loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":1, "Tome of water":1, "dragon harpoon":0}, name="tempoross, big harpoonfish")
    temp1 = tempoross(loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":0, "Tome of water":1, "dragon harpoon":1}, name="tempoross, dragon harpoon")
    temp2 = tempoross(loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":1, "Tome of water":1, "dragon harpoon":1}, name="\ntempoross, dragon harpoon + big harpoonfish")

    nextorvanihilvambraces = nex(loot_amount = {"Zaryte vambraces":1,"Torva full helm (damaged)":1,"Torva platebody (damaged)":1, "Torva platelegs (damaged)":1, "Nihil horn":1}, name= "Nex, torva + vambraces + nihil")
    nextorvavambraces = nex(loot_amount = {"Zaryte vambraces":1,"Torva full helm (damaged)":1,"Torva platebody (damaged)":1, "Torva platelegs (damaged)":1}, name= "Nex, torva + vambraces")
    nextorva = nex(loot_amount = {"Torva full helm (damaged)":1,"Torva platebody (damaged)":1, "Torva platelegs (damaged)":1}, name= "Nex, just torva")
    nex6man = nex(loot_amount = {"Zaryte vambraces":1,"Torva full helm (damaged)":1,"Torva platebody (damaged)":1, "Torva platelegs (damaged)":1, "Nihil horn":1, "Ancient hilt":1}, teamsize=6, name="nex, (assuming 6 man)")
    nex8man = nex(loot_amount = {"Zaryte vambraces":1,"Torva full helm (damaged)":1,"Torva platebody (damaged)":1, "Torva platelegs (damaged)":1, "Nihil horn":1, "Ancient hilt":1}, teamsize=8, name="nex, (assuming 8 man)")

    tob3man = theatre_of_blood(loot_amount = {"scythe of vitur":1, "grazi rapier":1,"sanguinesti staff":1, "justiciar faceguard":1, "justiciar chestguard":1, "justiciar legguard":1, "avernic hilt":1}, name="Theatre of blood (3 man)", teamsize=3)
    zalcano3tool = zalcano(loot_amount = {"crystal tool seed":3, "zalcano shard":0}, name="Zalcano 3 tool seeds")

    hardMode3man = theatre_of_blood_hard_mode(loot_amount = {"scythe of vitur":1, "grazi rapier":1,"sanguinesti staff":1, "justiciar faceguard":1, "justiciar chestguard":1, "justiciar legguard":1, "avernic hilt":1, "Sanguine dust":0, "Sanguine ornament kit":0,"holy ornament kit":0}, name="Theatre of blood hardmode (3 man)", teamsize=3)
    hardModeJustKits = theatre_of_blood_hard_mode(loot_amount = {"scythe of vitur":0, "grazi rapier":0,"sanguinesti staff":0, "justiciar faceguard":0, "justiciar chestguard":0, "justiciar legguard":0, "avernic hilt":0, "Sanguine dust":1, "Sanguine ornament kit":1,"holy ornament kit":1}, name="Theatre of blood hardmode kits", teamsize=3)
    hardMode3holy = theatre_of_blood_hard_mode(loot_amount = {"scythe of vitur":0, "grazi rapier":0,"sanguinesti staff":0, "justiciar faceguard":0, "justiciar chestguard":0, "justiciar legguard":0, "avernic hilt":0, "Sanguine dust":1, "Sanguine ornament kit":1,"holy ornament kit":3}, name="Theatre of blood hardmode 3 holy kits", teamsize=3)

    return [
        temp,
        temp1,
        temp2,
        pnightjustinq,
        pnightinq,
        pnight,
        krak,
        cg,
        cg1seed,
        hydra,
        hydra2,
        kq,
        dks,
        kbd,
        ven,
        ven2,
        ven3,
        cerb,
        cerb2,
        sire,
        corp,
        zul,
        zul2,
        night,
        vork,
        nextorvavambraces,
        nextorva,
        nextorvanihilvambraces,
        nex6man,
        tob3man,
        nex8man,
        zalcano3tool,
        ce,
        hardMode3man,
        hardModeJustKits,
        hardMode3holy
    ]

def allBosses():
    return [
        theatre_of_blood(),
        chambers_of_xeric(),
        theatre_of_blood_hard_mode(),
        barrows(),
        nex(),
        phosanis_nightmare(),
        tempoross(),
        nightmare(),
        grotesque_guardians(),
        abyssal_sire(),
        cave_kraken(),
        cerberus(),
        thermonuclear_smoke_devil(),
        alchemical_hydra(),
        chaos_fanatic(),
        crazy_archaeologist(),
        scorpia(),
        vetion(),
        venenatis(),
        callisto(),
        obor(),
        bryophyta(),
        mimic(),
        hespori(),
        zalcano(),
        wintertodt(),
        corrupted_gauntlet(),
        gauntlet(),
        dagannoth_rex(),
        dagannoth_supreme(),
        dagannoth_prime(),
        sarachnis(),
        kalphite_queen(),
        zulrah(),
        vorkath(),
        corporeal_beast(),
        commander_zilyana(),
        general_graardor(),
        kril_tsutsaroth(),
        kree_arra(),
        chaos_elemental(),
        theatre_of_blood_hard_mode(),
        guardians_of_the_rift()
    ]

def clues():
    return [
        easy_clues()
    ]