from operator import xor
import random
from matplotlib.pyplot import yscale
import numpy as np
from numpy.lib.function_base import average, median
from numpy.linalg import matrix_power
from scipy.sparse import csc_matrix
from scipy.sparse import coo_matrix

class monster:
    loot_odds = {}
    secondary_odds = {}
    tertiary_odds = {}
    quaternary_odds = {}
    kc_name = 'kc'

    def __init__(self, loot_tables=None, loot_amount=None, name=None):
        self.absorbingMatrix = None
        
        self.group_size = 1
        self.name = self.__class__.__name__
        if(loot_amount):
            self.loot_amount = loot_amount
            if(name):
                self.name = name

        for item, amount in self.loot_amount.items():
            self.loot_amount[item] = self.group_size * amount

        possible_loot = set(self.loot_odds.keys())
        if(loot_tables is not None):
            for table in loot_tables:
                possible_loot = possible_loot.union(set(table.keys()))

        if(not set(self.loot_amount.keys()).issubset(possible_loot)):
            raise AssertionError

        self.kc = 0
        self.loot_gotten = dict.fromkeys(possible_loot, 0)

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

    def contructMatrix(self, nStates, odds, dropArrayItems):
        data = []
        rowIndex = []
        colIndex = []
        for i in range(0,nStates):
            rowTotal = 0
            for index, item in enumerate(dropArrayItems):
                # skip if the item is not on this loottable
                if(not item in odds):
                    continue

                # skip if we already have the drop
                if((i >> index) & 1):
                    continue

                # If we need to collect multiple of 1 item we cannot get the second item before the first as we do not have 2 rolls
                if(index > 0 and dropArrayItems[index] == dropArrayItems[index-1] and not ((i >> index-1) & 1)):
                    continue

                # odds of going from state i 010b to state 011 (collected the 3rd item) = i+2**(ndrops - dropIndex)
                # we mirror the state by removing ndrops
                rowTotal += odds[item]
                data += [odds[item]]
                rowIndex += [i]
                colIndex += [i+2**index]

            # add the diagonal
            data += [1-rowTotal]
            rowIndex += [i]
            colIndex += [i]
        
        data = np.array(data)
        rowIndex = np.array(rowIndex, dtype='int')
        colIndex = np.array(colIndex, dtype='int')
        return coo_matrix((data, (rowIndex, colIndex)), shape=(nStates,nStates)).tocsc()
        


    def convertToMarkovChain(self):
        nDrops = sum(self.loot_amount.values())
        nStates = 2 ** nDrops
        
        # list all the items we need to get
        try:
            dropArrayItems = [[item] * amount for item, amount in self.loot_amount.items()]
        except:
            print(self.loot_amount.items())
            return
        # flatten
        dropArrayItems = [item for sublist in dropArrayItems for item in sublist]

        # generate tables for all loot tables
        m1 = self.contructMatrix(nStates, self.loot_odds, dropArrayItems)
        m2 = self.contructMatrix(nStates, self.secondary_odds, dropArrayItems)
        m3 = self.contructMatrix(nStates, self.tertiary_odds, dropArrayItems)
        m4 = self.contructMatrix(nStates, self.quaternary_odds, dropArrayItems)

        # getting 4 different rolls is just the odds multiplied together
        self.absorbingMatrix = m1 * m2 * m3 * m4

    def getAbsorbingMatrixGraph(self):
        copy = self.absorbingMatrix.copy()
        (width, _) = copy.shape
        finalState = (0,width - 1)
        y = [copy[finalState]]
        while(copy[finalState] < 0.9999):
            copy *= self.absorbingMatrix
            y += [copy[finalState]]
        x = [i for i in range(1,len(y)+1)]

        # y index is [kc-1] compensate for that
        half = next(i[0] for i in enumerate(y) if i[1] > 0.5) + 1
        
        y = [(j - y[it-1])*100 for it,j in enumerate(y)]
        
        average = sum(xi * yi/100 for xi, yi in zip(x,y))
        y[0] = self.absorbingMatrix[finalState] * 100

        mode = y.index(max(y)) + 1

        return x, y, mode, half, average


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
    loot_odds = {"dragonbone necklace":1/1000,"wyvern visage":1/5000,"draconic visage":1/5000}
    loot_amount = {"dragonbone necklace":1,"wyvern visage":1,"draconic visage":0}

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
    loot_odds = {"inquisitor's great helm":1/960,"inquisitor's hauberk":1/960,"inquisitor's plateskirt":1/960, "inquisitor's mace":1/1920, "nightmare staff":1/640}
    secondary_odds = {"eldritch orb":1/2880, "harmonised orb":1/2880,"volatile orb":1/2880}
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
    loot_odds = {"inquisitor's great helm":1/960,"inquisitor's hauberk":1/960,"inquisitor's plateskirt":1/960, "inquisitor's mace":1/1920, "nightmare staff":1/640}
    secondary_odds = {"eldritch orb":1/2880, "harmonised orb":1/2880,"volatile orb":1/2880}
    loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":1, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}
    
    def __init__(self, teamsize=1, **kwargs):
        kwargs["loot_tables"] = [self.secondary_odds]
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

class theatre_of_blood(monster):
    #https://twitter.com/JagexKieren/status/1145376451446751232/photo/1
    team_size = 4
    max_points = 68
    death_point_cost = 4
    base_odds = 1/9.1
    personal_points = 17
    total_deaths = 0

    total_points = max_points - death_point_cost * total_deaths
    odds_adjustment = base_odds * total_points/max_points * personal_points/total_points

    loot_odds = {"scythe of vitur":1/19, "grazi rapier":2/19,"sanguinesti staff":2/19, "justiciar faceguard":2/19, "justiciar chestguard":2/19, "justiciar legguard":2/19, "avernic hilt":8/19}
    for drop in loot_odds:
        loot_odds[drop] *= odds_adjustment
    loot_amount = {"scythe of vitur":1, "grazi rapier":1,"sanguinesti staff":1, "justiciar faceguard":1, "justiciar chestguard":1, "justiciar legguard":1, "avernic hilt":1}


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

hydra = alchemical_hydra(loot_amount={"ring piece":3,"hydra tail":1,"hydra leather":1,"hydra's claw":1,"dragon thrownaxe":0,"dragon knife":0}, name="hydra + brimstone ring")
hydra2 = alchemical_hydra(loot_amount={"ring piece":3,"hydra tail":1,"hydra leather":1,"hydra's claw":1,"dragon thrownaxe":1,"dragon knife":1}, name="hydra + brimstone ring + knives&axes")
krak = cave_kraken(loot_amount={"kraken tentacle":11, "trident of the seas (full)":1}, name="kraken + 11 tents")
kq = kalphite_queen(loot_amount={"dragon chain":1,"dragon 2h sword":1}, name= "kq chain+2h")
kbd = king_black_dragon(loot_amount={"dragon pickaxe":1, "draconic visage":1/5000}, name="kbd visage + pick")
ven = venenatis(loot_amount={"treasonous ring":1,"dragon pickaxe":1,"dragon 2h sword":1}, name="Wildy boss, ring + pick + 2h")
ven2 = venenatis(loot_amount={"treasonous ring":1,"dragon pickaxe":1,"dragon 2h sword":0}, name="Wildy boss, ring + pick")
ven3 = venenatis(loot_amount={"treasonous ring":0,"dragon pickaxe":1,"dragon 2h sword":0}, name="Wildy boss just the d pick")
cerb = cerberus(loot_amount = {"primordial crystal":1,"pegasian_crystal":1,"eternal crystal":1,"smouldering stone":1}, name="cerb + 1 smouldering")
cerb2 = cerberus(loot_amount = {"primordial crystal":1,"pegasian_crystal":1,"eternal crystal":1,"smouldering stone":3}, name= "cerb + 3 smouldering")
sire = abyssal_sire(loot_amount = {"bludgeon piece":3, "abyssal dagger":1}, name= "sire + dagger")
dks = dkings(name="dks")
corp = corporeal_beast(loot_amount = {"arcane sigil":1,"spectral sigil":1,"elysian sigil":1,"spirit shield":3,"holy elixer":3}, name = "corp + 3 blessed shields")
zul = zulrah(loot_amount = {"tanzanite fang":1,"magic fang":1,"serpentine visage":1,"uncut onyx":1, "magma mutagen":1, "tanzanite mutagen":1}, name="zulrah + onyx + mutagens")
zul2 = zulrah(loot_amount = {"tanzanite fang":1,"magic fang":2,"serpentine visage":1,"uncut onyx":0, "magma mutagen":0, "tanzanite mutagen":0}, name="zulrah, 2 magic fangs")
night = nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":3, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}, name="nightmare 3 staves")
pnight = phosanis_nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":3, "eldritch orb":1, "harmonised orb":1,"volatile orb":1}, name="phosanis nightmare 3 staves")
pnightinq = phosanis_nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":0, "eldritch orb":0, "harmonised orb":0,"volatile orb":0}, name="phosanis nightmare full inq + mace")
pnightjustinq = phosanis_nightmare(loot_amount = {"inquisitor's great helm":1,"inquisitor's hauberk":1,"inquisitor's plateskirt":1, "inquisitor's mace":1, "nightmare staff":0, "eldritch orb":0, "harmonised orb":0,"volatile orb":0}, name="phosanis nightmare full inq, no mace")
vork = vorkath(loot_amount = {"dragonbone necklace":1,"wyvern visage":1,"draconic visage":1}, name="vork both visages")
cg = corrupted_gauntlet(loot_amount={"enhanced crystal weapon seed":2, "crystal armour seed":6}, name="Corrupted gauntlet 2 enhanced weapon seeds, 6 armour crystals")


temp = tempoross(loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":1, "Tome of water":1, "dragon harpoon":0}, name="tempoross + big harpoonfish")
temp1 = tempoross(loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":0, "Tome of water":1, "dragon harpoon":1}, name="tempoross + dragon harpoon")
temp2 = tempoross(loot_amount = {"soaked page":1, "fish barrel":1, "tackle box":1, "big harpoonfish":1, "Tome of water":1, "dragon harpoon":1}, name="\ntempoross + dragon harpoon + big harpoonfish")

complete_drops = [pnightjustinq, pnightinq, cg, hydra, hydra2, krak, kq, dks, ven, ven2, ven3, cerb, cerb2, sire, corp, zul, zul2, pnight, night, vork, temp, temp1, temp2]
all_bosses = [phosanis_nightmare(), tempoross(), nightmare(), grotesque_guardians(), abyssal_sire(), cave_kraken(), cerberus(), thermonuclear_smoke_devil(), alchemical_hydra(), chaos_fanatic(), crazy_archaeologist(), scorpia(), vetion(), venenatis(), callisto(), obor(), bryophyta(), mimic(), hespori(), zalcano(), wintertodt(), corrupted_gauntlet(), gauntlet(), dagannoth_rex(), dagannoth_supreme(), dagannoth_prime(), sarachnis(), kalphite_queen(), zulrah(), vorkath(), corporeal_beast(), commander_zilyana(), general_graardor(), kril_tsutsaroth(), kree_arra(), theatre_of_blood(), chambers_of_xeric()]