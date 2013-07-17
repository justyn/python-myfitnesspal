import os.path
import re

import lxml.html
import requests

from myfitnesspal.base import MFPBase
from myfitnesspal.day import Day
from myfitnesspal.entry import Entry
from myfitnesspal.meal import Meal


class Client(MFPBase):
    BASE_URL = 'http://www.myfitnesspal.com/'
    LOGIN_PATH = 'account/login'
    ABBREVIATIONS = {
        'carbs': 'carbohydrates',
    }

    def __init__(self, username, password, login=True):
        self.username = username
        self.password = password

        self.session = requests.Session()
        if login:
            self._login()

    def _login(self):
        login_url = os.path.join(self.BASE_URL, self.LOGIN_PATH)
        document = self._get_document_for_url(login_url)
        authenticity_token = document.xpath(
            "(//input[@name='authenticity_token']/@value)[1]"
        )[0]
        utf8_field = document.xpath(
            "(//input[@name='utf8']/@value)[1]"
        )[0]

        self.session.post(
            login_url,
            data={
                'utf8': utf8_field,
                'authenticity_token': authenticity_token,
                'username': self.username,
                'password': self.password,
            }
        )

    def _get_full_name(self, raw_name):
        name = raw_name.lower()
        if name not in self.ABBREVIATIONS:
            return name
        return self.ABBREVIATIONS[name]

    def _get_url_for_date(self, date):
        return os.path.join(
            self.BASE_URL,
            'food/diary',
            self.username,
        ) + '?date=%s' % (
            date.strftime('%Y-%m-%d')
        )

    def _get_content_for_url(self, url):
        return self.session.get(url).content.decode('utf8')

    def _get_document_for_url(self, url):
        content = self._get_content_for_url(url)

        return lxml.html.document_fromstring(content)

    def _get_numeric(self, string):
        return int(re.sub(r'[^\d.]+', '', string))

    def _get_fields(self, document):
        meal_header = document.xpath("//tr[@class='meal_header']")[0]
        tds = meal_header.findall('td')
        fields = ['name']
        for field in tds[1:]:
            fields.append(
                self._get_full_name(
                    field.text
                )
            )
        return fields

    def _get_goals(self, document):
        total_header = document.xpath("//tr[@class='total']")[0]
        goal_header = total_header.getnext()  # The following TR contains goals
        columns = goal_header.findall('td')

        fields = self._get_fields(document)

        nutrition = {}
        for n in range(1, len(columns)):
            column = columns[n]
            try:
                nutr_name = fields[n]
            except IndexError:
                # This is the 'delete' button
                continue
            nutrition[nutr_name] = self._get_numeric(column.text)

        return nutrition

    def _get_meals(self, document):
        meals = []
        fields = None
        meal_headers = document.xpath("//tr[@class='meal_header']")

        for meal_header in meal_headers:
            tds = meal_header.findall('td')
            meal_name = tds[0].text.lower()
            if fields is None:
                fields = self._get_fields(document)
            this = meal_header
            entries = []

            while True:
                this = this.getnext()
                if not this.attrib.get('class') is None:
                    break
                columns = this.findall('td')
                name = columns[0].find('a').text
                nutrition = {}

                for n in range(1, len(columns)):
                    column = columns[n]
                    try:
                        nutr_name = fields[n]
                    except IndexError:
                        # This is the 'delete' button
                        continue
                    nutrition[nutr_name] = self._get_numeric(column.text)

                entries.append(
                    Entry(
                        name,
                        nutrition,
                    )
                )

            meals.append(
                Meal(
                    meal_name,
                    entries,
                )
            )

        return meals

    def get_date(self, date):
        document = self._get_document_for_url(
            self._get_url_for_date(
                date
            )
        )

        meals = self._get_meals(document)
        goals = self._get_goals(document)

        day = Day(
            date=date,
            meals=meals,
            goals=goals,
        )

        return day

    def __unicode__(self):
        return u'MyFitnessPal Client for %s' % self.username
