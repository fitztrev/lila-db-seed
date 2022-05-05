import random
import bson
import base64
import pymongo
from modules.event import evt
from modules.datasrc import gen
import modules.util as util


def create_game_colls(db: pymongo.MongoClient, num_games: int) -> None:
    if num_games == 0:
        return
    elif num_games < 0:
        num_games = len(gen.games)
    elif num_games < len(gen.games):
        gen.games = gen.games[:num_games]

    games: list[game.Game] = []
    crosstable: dict[str, Result] = {}

    for bson_game in gen.games:

        us = random.sample(gen.uids, 2)
        g = Game(bson_game, us[0], us[1])
        games.append(g)
        evt.add_game(
            us[0], g.ca, us[1], g.outcome(us[0]), g._id + g.__dict__["is"][0:4]
        )
        evt.add_game(
            us[1], g.ca, us[0], g.outcome(us[1]), g._id + g.__dict__["is"][4:]
        )

        id: str = f"{us[0]}/{us[1]}" if us[0] < us[1] else f"{us[1]}/{us[0]}"
        crosstable.setdefault(id, Result(id)).add_game(g)

    util.bulk_write(db.game5, games)
    util.bulk_write(db.puzzle2_path, gen.puzzle_paths)
    util.bulk_write(db.puzzle2_puzzle, gen.puzzles)
    # TODO find out why crosstable and matchup are separate slices of what
    # could be same collection
    util.bulk_write(db.crosstable2, crosstable.values())
    util.bulk_write(db.matchup, crosstable.values())


def drop(db: pymongo.MongoClient) -> None:
    db.game5.drop()
    db.puzzle2_path.drop()
    db.puzzle2_puzzle.drop()
    db.crosstable2.drop()
    db.matchup.drop()


class Game:
    def __init__(self, game: dict, white: str, black: str):
        self._id = game["_id"]
        self.us = [white, black]
        self.__dict__["is"] = _next_pid(True) + _next_pid(False)
        self.p0 = game["p0"]
        self.p1 = game["p1"]
        self.s = game["s"]
        self.t = game["t"]
        self.v = 1
        self.ra = game["ra"]
        self.ca = util.time_since_days_ago(730)
        self.ua = util.time_shortly_after(self.ca)
        self.so = game["so"]
        self.hp = bson.binary.Binary(game["hp"])
        self.an = game["an"]
        if "c" in game:
            self.c = bson.binary.Binary(game["c"])
        if "cw" in game:
            self.cw = bson.binary.Binary(game["cw"])
        if "cb" in game:
            self.cb = bson.binary.Binary(game["cb"])
        if "w" in game:
            self.w = game["w"]
            self.wid = white if game["w"] else black

    def outcome(self, player: str):
        if not hasattr(self, "w"):
            return evt.Outcome.DRAW
        elif self.wid == player:
            return evt.Outcome.WIN
        else:
            return evt.Outcome.LOSS


_pidseed: int = 1


def _next_pid(white: bool) -> str:
    global _pidseed
    pid = (_pidseed << 6) | (0x0020 if white else 0x0000)
    _pidseed = _pidseed + 1
    return base64.b64encode(pid.to_bytes(3, "big")).decode("ascii")[:4]


class Result:
    def __init__(self, id: str):
        self._id = id
        self.r = []
        self.s1 = 0
        self.s2 = 0

    def add_game(self, game: Game):
        if hasattr(game, "w"):
            if self._id.startswith(game.wid):
                flag = ""
                self.s1 = self.s1 + 10
            else:
                flag = "-"
                self.s2 = self.s2 + 10
        else:
            flag = "="
            self.s1 = self.s1 + 5
            self.s2 = self.s2 + 5
        self.r.append(game._id + flag)
        self.d = game.ca
