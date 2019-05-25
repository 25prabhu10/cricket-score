import time

from src.utils import handlerequests

IST_SECONDS = ((5 * 60 * 60) + (30 * 60))


class Cricbuzz():
    def __init__(self):
        self.URL = 'http://mapps.cricbuzz.com/cbzios/match/'

    def crawl_url(self, url):
        return handlerequests.request_json(url)

    def getSeries(self, sid):
        series = {}
        series['id'] = sid
        url = f'http://mapps.cricbuzz.com/cbzios/series/{sid}/matches'
        return self.crawl_url(url)

    def players_mapping(self, mid, match=None):
        if mid:
            url = self.URL + str(mid)
            match = self.crawl_url(url)
        players = match.get('players')
        data = {}
        for p in players:
            data[int(p['id'])] = p['name']
        teams = {}
        teams[int(match.get('team1').get('id'))
              ] = match.get('team1').get('name')
        teams[int(match.get('team2').get('id'))
              ] = match.get('team2').get('name')
        return data, teams

    def matchinfo(self, mid):
        url = self.URL + str(mid)
        match = self.crawl_url(url)
        utc_hours, utc_minutes = [int(x) for x in match.get(
            'venue').get('timezone').split(':')]
        utc_seconds = ((utc_hours * 60 * 60) + (utc_minutes * 60))
        from_epoch = int(match.get('header').get(
            'start_time')) - IST_SECONDS + utc_seconds
        match['header']['start_time_'] = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(from_epoch))

        # squads
        p_map, _ = self.players_mapping(mid=None, match=match)
        team1 = {}
        team1['name'] = match.get('team1').get('name')
        t1_s = match.get('team1').get('squad')
        if t1_s is None:
            t1_s = []
        team1['squad'] = [p_map[id] for id in t1_s]
        t1_s_b = match.get('team1').get('squad_bench')
        if t1_s_b is None:
            t1_s_b = []
        team1['squad_bench'] = [p_map[id] for id in t1_s_b]
        team2 = {}
        team2['name'] = match.get('team2').get('name')
        t2_s = match.get('team2').get('squad')
        if t2_s is None:
            t2_s = []
        team2['squad'] = [p_map[id] for id in t2_s]
        t2_s_b = match.get('team2').get('squad_bench')
        if t2_s_b is None:
            t2_s_b = []
        team2['squad_bench'] = [p_map[id] for id in t2_s_b]
        match['team1_'] = team1
        match['team2_'] = team2
        return match

    def matches(self):
        url = self.URL + 'livematches'
        crawled_content = self.crawl_url(url)
        matches = crawled_content['matches']
        info = []

        for match in matches:
            info.append(self.matchinfo(match['match_id']))
        return info

    def _find_match(self, id):
        url = self.URL + 'livematches'
        crawled_content = self.crawl_url(url)
        matches = crawled_content['matches']

        for match in matches:
            if match['match_id'] == id:
                return match
        return None

    def livescore(self, mid):
        data = {}
        try:
            comm = self._find_match(mid)

            batting = comm.get('bat_team')
            if batting is None:
                return data
            bowling = comm.get('bow_team')
            batsman = comm.get('batsman')
            bowler = comm.get('bowler')

            team_map = {}
            team_map[comm["team1"]["id"]] = comm["team1"]["name"]
            team_map[comm["team2"]["id"]] = comm["team2"]["name"]

            if batsman is None:
                batsman = []
            if bowler is None:
                bowler = []
            d = {}
            d['team'] = team_map[batting.get('id')]
            d['score'] = []
            d['batsman'] = []
            for player in batsman:
                d['batsman'].append({'name': player['name'], 'runs': player['r'],
                                     'balls': player['b'], 'fours': player['4s'], 'six': player['6s']})
            binngs = batting.get('innings')
            if binngs is None:
                binngs = []
            for inng in binngs:
                d['score'].append({'inning_num': inng['id'], 'runs': inng['score'],
                                   'wickets': inng['wkts'], 'overs': inng['overs'], 'declare': inng.get('decl')})
            data['batting'] = d
            d = {}
            d['team'] = team_map[bowling.get('id')]
            d['score'] = []
            d['bowler'] = []
            for player in bowler:
                d['bowler'].append({'name': player['name'], 'overs': player['o'],
                                    'maidens': player['m'], 'runs': player['r'], 'wickets': player['w']})
            bwinngs = bowling.get('innings')
            if bwinngs is None:
                bwinngs = []
            for inng in bwinngs:
                d['score'].append({'inning_num': inng['id'], 'runs': inng['score'],
                                   'wickets': inng['wkts'], 'overs': inng['overs'], 'declare': inng.get('decl')})
            data['bowling'] = d
            return data
        except AttributeError:
            print('Not Live')

    def commentary(self, mid):
        data = {}
        try:
            url = self.URL + mid + '/commentary'
            comm = self.crawl_url(url).get('comm_lines')
            d = []
            for c in comm:
                if "comm" in c:
                    d.append({"comm": c.get("comm"), "over": c.get("o_no")})
            data['commentary'] = d
            return data
        except Exception:
            raise

    def scorecard(self, mid):
        try:
            url = self.URL + mid + '/scorecard.json'
            scard = self.crawl_url(url)
            p_map, t_map = self.players_mapping(mid)

            innings = scard.get('Innings')
            data = {}
            d = []
            card = {}
            for inng in innings:
                extras = inng.get("extras").copy()
                inng["extras"] = {"total": extras.get("t"), "byes": extras.get("b"), "lbyes": extras.get(
                    "lb"), "wides": extras.get("wd"), "noballs": extras.get("nb"), "penalty": extras.get("p")}
                batplayers = inng.get('batsmen')
                if batplayers is None:
                    batplayers = []
                batsman = []
                bowlers = []
                fow = []
                for player in batplayers:
                    status = player.get('out_desc')
                    p_name = p_map[int(player.get('id'))]
                    batsman.append({'name': p_name, 'runs': player['r'], 'balls': player['b'],
                                    'fours': player['4s'], 'six': player['6s'], 'dismissal': status})
                card['batcard'] = batsman
                card['bowlteam'] = t_map[int(inng.get("bowl_team_id"))]
                bowlplayers = inng.get('bowlers')
                if bowlplayers is None:
                    bowlplayers = []
                for player in bowlplayers:
                    p_name = p_map[int(player.get('id'))]
                    bowlers.append({'name': p_name, 'overs': player['o'], 'maidens': player['m'],
                                    'runs': player['r'], 'wickets': player['w'], 'wides': player['wd'], 'nballs': player['n']})
                card['bowlcard'] = bowlers
                fall_wickets = inng.get("fow")
                if fall_wickets is None:
                    fall_wickets = []
                for p in fall_wickets:
                    p_name = p_map[int(p.get('id'))]
                    fow.append({"name": p_name, "wkt_num": p.get(
                        "wkt_nbr"), "score": p.get("score"), "overs": p.get("over")})
                card["fall_wickets"] = fow
                d.append(card.copy())
            data['scorecard'] = d
            return data, scard
        except Exception:
            raise

    def full_match(self, mid):
        url = self.URL + str(mid) + '/graphs.json'
        return self.crawl_url(url)
