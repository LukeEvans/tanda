#!/usr/bin/python

import calendar
import os

import math
import time

from stravalib.client import Client
from datetime import datetime, timedelta
from flask import Flask, redirect, request, jsonify, url_for, make_response, session

client_id = os.environ.get("APP_ID")
client_secret = os.environ.get("APP_SECRET")

#           Google
HOST = "<google host name>"

#             Local
# HOST = "http://localhost:5000"
# secret = "APP_SECRET"

app = Flask(__name__)

PERIOD_WEEKS = 8
PRIMARY_ACTIVITY = "Run"

athletes = {}


def km_to_mile(km):
    return km * 0.621371


def seconds_to_string(seconds):
    return time.strftime('%H:%M:%S', time.gmtime(seconds)).lstrip("00:")


def to_seconds(time_string):
    hours, minutes, seconds = str(time_string).split(':')
    return (int(hours) * 3600) + (int(minutes) * 60) + int(seconds)


def fetch_activities(client, before, after):
    activities = []

    for activity in client.get_activities(before=before, after=after):
        if activity.type == PRIMARY_ACTIVITY:
            activities.append(activity)

    return activities


def calculate_tanda_seconds(km_per_week, mean_pace):
    km_per_hour = (1 / mean_pace) * 60 * 60
    return (12 + (98.5 * (math.e ** (km_per_week / -189))) + (1390 / km_per_hour)) * 60


def half_marathon_from_marathon(marathon_time):
    return (marathon_time - 600) / 2


def get_tanda(client, target_date):
    first_date = datetime.strptime(target_date, '%Y-%m-%d') - timedelta(weeks=PERIOD_WEEKS)
    activities = fetch_activities(client, target_date, first_date)

    total_km = 0
    total_seconds = 0

    for activity in activities:
        total_km = total_km + (activity.distance.num / 1000)
        total_seconds = total_seconds + to_seconds(activity.moving_time)

    total_miles = km_to_mile(total_km)

    km_per_week = total_km / PERIOD_WEEKS
    miles_per_week = "{:.0f}".format(km_to_mile(km_per_week))

    mean_pace = total_seconds / total_km
    mean_mile_pace = seconds_to_string(total_seconds / total_miles)

    marathon_time_seconds = calculate_tanda_seconds(km_per_week, mean_pace)
    half_marathon_time = seconds_to_string(half_marathon_from_marathon(marathon_time_seconds))
    marathon_time = seconds_to_string(marathon_time_seconds)

    print("---------------------------------------------------")
    print(f"Average Miles Per Week: {miles_per_week}")
    print(f"Average Pace Per Mile: {mean_mile_pace}")
    print(f"Estimated Half-Marathon Time: {half_marathon_time}")
    print(f"Estimated Marathon Time: {marathon_time}")
    print("---------------------------------------------------")

    return {'marathon_time': marathon_time, 'half_marathon_time': half_marathon_time, 'average_mpw': miles_per_week,
            'average_pace': mean_mile_pace}


def client_for_athlete(user_name):
    athlete = athletes[user_name]
    return Client(access_token=athlete['access_token'])


def expired(expires_at):
    if not expires_at:
        return True

    current_time = calendar.timegm(time.gmtime())
    return current_time >= expires_at


def refresh(user_name):
    athlete = athletes[user_name]
    client = client_for_athlete(user_name)
    refresh_response = client.refresh_access_token(client_id=client_id, client_secret=client_secret,
                                                   refresh_token=athlete['refresh_token'])
    print(f"Setting athlete: {user_name} data to: {refresh_response}")
    athletes[user_name] = refresh_response


@app.route('/tanda/<user_name>')
def tanda(user_name):
    print(f"Getting tanda for athlete {user_name}")
    target_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    athlete = athletes.get(user_name)
    print(athlete)

    if not athlete:
        print(f"First authorization for athlete: {user_name}")
        auth_url = f'{HOST}/authorized?athlete={user_name}'
        authorize_url = Client().authorization_url(client_id=client_id, redirect_uri=auth_url)
        return redirect(authorize_url)

    if expired(athlete['expires_at']):
        print("Auth expired. Refreshing")
        refresh(user_name)

    client = client_for_athlete(user_name)
    return jsonify(get_tanda(client, target_date))


@app.route('/')
def index():
    return redirect(url_for('tanda', user_name='levans'))


@app.route('/authorized')
def callback():
    code = request.args['code']
    athlete = request.args['athlete']

    token_response = Client().exchange_code_for_token(client_id=client_id, client_secret=client_secret, code=code)

    print(f"Setting athlete: {athlete} data to: {token_response}")
    athletes[athlete] = token_response

    return redirect(url_for('tanda', user_name=athlete))


app.secret_key = 'APP_SECRET_KEY'

if __name__ == '__main__':
    app.run()
