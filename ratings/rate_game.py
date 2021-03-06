from bson.objectid import ObjectId
import click
import ConfigParser
import datetime
from pymongo import MongoClient
import sys
import trueskill

config = ConfigParser.SafeConfigParser(
    {'connect': 'mongodb://localhost/', 'db': 'pugchamp', 'rating_base': '1500'})
config.read('settings.cfg')

client = MongoClient(config.get('config', 'connect'))
db = client[config.get('config', 'db')]

rating_base = config.getfloat('config', 'rating_base')
trueskill.setup(mu=rating_base, sigma=rating_base / 3,
                beta=rating_base / 6, tau=rating_base / 300, backend='mpmath')


@click.command()
@click.argument('game_id')
def rate_game(game_id):
    game = db.games.find_one({'_id': ObjectId(game_id)})

    old_ratings = []
    weights = {}

    for index, team in enumerate(game['teams']):
        old_team_ratings = {}

        for role in team['composition']:
            for player in role['players']:
                user = db.users.find_one(player['user'])

                if 'stats' in user and 'rating' in user['stats'] and 'mean' in user['stats']['rating']:
                    rating = trueskill.Rating(mu=user['stats']['rating']['mean'], sigma=user[
                                              'stats']['rating']['deviation'])
                else:
                    rating = trueskill.Rating()

                old_team_ratings[user['_id']] = rating
                if ('duration' in game and game['duration'] != 0):
                    weights[(index, user['_id'])] = player[
                        'time'] / game['duration']

        old_ratings.append(old_team_ratings)

    high_score = max(game['score'])
    ranks = [high_score - score for score in game['score']]

    new_ratings = trueskill.rate(old_ratings, ranks=ranks, weights=weights)

    for index, team in enumerate(game['teams']):
        for role in team['composition']:
            for player in role['players']:
                old_rating = old_ratings[index][player['user']]
                new_rating = new_ratings[index][player['user']]

                db.ratings.insert_one({'user': player['user'], 'date': game['date'], 'game': game['_id'], 'before': {
                                      'mean': old_rating.mu, 'deviation': old_rating.sigma}, 'after': {'mean': new_rating.mu, 'deviation': new_rating.sigma}})

if __name__ == '__main__':
    rate_game()
