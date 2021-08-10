import time
import asyncio
from classes import DictToDeck


"""
    Here, the user presents a .txt file with german verbs
    on each line to get back a json type anki deck that stores
    all the verbs with their conjugation and two different
    sentence examples in both german and english by default
    or french.

    10/08/2021 Update
    This is no longer working because i've written this way back
    when i just started and i didn't save what versions were
    being used of python or other libiraries.
    

"""

start = time.perf_counter()

default = DictToDeck()

verbs = default.file_verbs('verbs.txt', 10)
asyncio.run(default.get_results(verbs))
default.dump_jsfile('verbsdata.json', default.results)
default.results_to_jsdeck('deck.json')


elapsed = time.perf_counter() - start
print(f"Average time per verb is {elapsed / len(verbs):0.4f} for {len(verbs)} verbs")
print(f"{__file__} executed in {elapsed:0.4f} seconds.")
