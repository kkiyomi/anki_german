from bs4 import BeautifulSoup
import json
import asyncio
import aiohttp
import re
import uuid


class Options(object):
    def json_format(self, *items):
        for item in items:
            json_format = json.dumps(item, indent=4, ensure_ascii=False)
            print(json_format)

    async def fetch(self, session, url):
        async with session.get(url) as response:
            return await response.text()

    async def fetch_urls(self, url_list):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url in url_list:
                task = asyncio.create_task(self.fetch(session, url))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
        return responses

    async def fetch_resp(self, words):
        url_list = [self.base_url.replace("XXXXXX", word) for word in words]
        responses = await self.fetch_urls(url_list)
        return responses


class DeVerbs(Options):
    def __init__(self):
        super(DeVerbs, self).__init__()
        self.base_url = (
            "https://konjugator.reverso.net/konjugation-deutsch-verb-XXXXXX.html"
        )
        self.lists_needed = [
            "Indikativ Präsens",
            "Indikativ Präteritum",
            "Infinitiv Perfekt",
        ]
        self.seperator = "/"

    def get_verb(self, response):
        soup = BeautifulSoup(response, "html.parser")

        error = soup.find(attrs={"class": "errorv"})
        unknown = soup.find(attrs={"class": "unknown-word-warning"})
        if unknown or error:
            return

        # get the correct word in case of a missing umlaut or typo
        self.verb = soup.find(attrs={"class": "targetted-word-wrap"}).text.strip()
        anki_konj = {"verb": f"{self.verb}"}

        blocks = soup.find_all(attrs={"mobile-title": self.lists_needed})

        verbformen = [self.get_verbform(block) for block in blocks]
        anki_konj["Verbformen"] = self.seperator.join(verbformen)
        return anki_konj

    def get_verbform(self, block):
        try:
            Verbform = block.find(
                string=re.compile("er/sie/es")
            ).parent.next_sibling.text.strip()
        except AttributeError:
            Perfekt = [line.text for line in block.find_all("li")]
            if len(Perfekt) == 1:
                Verbform = self.seperator.join(Perfekt)
            elif Perfekt[0].split()[0] == Perfekt[1].split()[0]:
                #   in case of perfekt like "gefahren sein, haben"
                Verbform = f"{Perfekt[0].split()[0]} {Perfekt[0].split()[1]}, {Perfekt[1].split()[1]}"
            elif Perfekt[0].split()[1] == Perfekt[1].split()[1]:
                #   in case of perfekt like "überholt, übergeholt haben"
                Verbform = f"{Perfekt[0].split()[0]}, {Perfekt[1].split()[0]} {Perfekt[1].split()[1]}"
            else:
                Verbform = self.seperator.join(Perfekt)
        return Verbform


class Examples(Options):
    def __init__(self, language="en"):
        super(Examples, self).__init__()

        if language == "fr":
            self.base_url = (
                f"https://context.reverso.net/übersetzung/deutsch-franzosisch/XXXXXX"
            )
        elif language == "en":
            self.base_url = (
                f"https://context.reverso.net/übersetzung/deutsch-englisch/XXXXXX"
            )

    def get_examples(self, response):

        soup = BeautifulSoup(response, "html.parser")

        self.word = soup.find(attrs={"class": "title-content"}).text.split('"')[1]
        anki_name = {"word": f"{self.word}"}

        try:
            english_translations = soup.find(attrs={"id": "translations-content"})
            english_trans = english_translations.find_all("a", limit=2)
            if not english_trans:
                english_trans = english_translations.find_all(limit=2)
            de_sentence = soup.find_all(attrs={"class": "src ltr"}, limit=2)
            en_sentence = soup.find_all(attrs={"class": "trg ltr"}, limit=2)
        except AttributeError:
            print(f"The word '{self.word}' can not be found. Skipped.")
            return

        anki_name["english_translation"] = [
            english_tr.text.strip() for english_tr in english_trans
        ]
        anki_name["DE sentences"] = [de.text.strip() for de in de_sentence]
        anki_name["EN sentences"] = [en.text.strip() for en in en_sentence]

        return anki_name


class DictToDeck:
    def __init__(self, language="en"):
        super().__init__()
        self.deck = self.load_jsfile(f"deck_{language}_sample.json")
        self.language = language
        self.results = []
        self.template = json.loads(
            """{
            "__type__": "Note",
            "data": "",
            "fields": [],
            "flags": 0,
            "guid": "",
            "newlyAdded": true,
            "note_model_uuid": "f77f193d-598b-11ea-ba0f-1867b089b138",
            "tags": []
        }"""
        )

    def load_jsfile(self, filename):
        with open(filename, encoding="utf8") as outfile:
            return json.load(outfile)

    def dump_jsfile(self, filename, item):
        with open(filename, "w", encoding="utf8") as write_file:
            json.dump(item, write_file, indent=4, ensure_ascii=False)

    def file_verbs(self, filename, limit=None):
        with open(filename, encoding="utf8") as f:
            contents = f.readlines()
            words = [content.strip() for content in contents[:limit]]
            return words

    def get_notes(self):
        self.deck["notes"] = []

        for item in self.results:
            fields = []
            seperator = "/"
            try:
                fields.append(item["verb"])
                fields.append(seperator.join(item["english_translation"]))
                fields.append(item["Verbformen"])
                for x, y in zip(item["DE sentences"], item["EN sentences"]):
                    fields.append(x)
                    fields.append(y)
            except KeyError:
                continue
            self.template["fields"] = fields[:]
            self.template["guid"] = str(uuid.uuid4().hex)
            self.deck["notes"].append(dict(self.template))

    async def get_results(self, words):
        responses = await DeVerbs().fetch_resp(words)
        ex_responses = await Examples(self.language).fetch_resp(words)

        for response, ex_response in zip(responses, ex_responses):
            anki_verb = DeVerbs().get_verb(response)
            anki_example = Examples().get_examples(ex_response)

            if anki_verb and anki_example:
                del anki_example["word"]
                anki_name = {**anki_verb, **anki_example}
                self.results.append(anki_name)
                message = f"Verb '{anki_name['verb']}' and its example are done, doing next one."

            elif anki_verb:
                self.results.append(anki_verb)
                message = f"Verb '{anki_name['verb']}' is done, doing next one."

            elif anki_example:
                self.results.append(anki_example)
                message = f"Nomen '{anki_example['word']}' and its example are  done, doing next one."

            else:
                continue
            message += f" {len(responses) - responses.index(response)} words remaining."
            print(message)

    def results_to_jsdeck(self, filename):
        self.get_notes()
        self.dump_jsfile(filename, self.deck)
