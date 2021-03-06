# -*- coding: utf-8 -*-
#
# Copyright (©) 2010-2013 Estêvão Samuel Procópio
# Copyright (©) 2010-2013 Gustavo Noronha Silva
# Copyright (©) 2014 Lúcio Flávio Corrêa
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime, date
import time
import requests
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
from montanha.models import Mandate, CollectionRun, ArchivedExpense


class BaseCollector(object):
    def __init__(self, collection_runs, debug_enabled):
        self.debug_enabled = debug_enabled
        self.collection_runs = collection_runs
        self.collection_run = None

        self.default_timeout = 20
        self.max_tries = 10
        self.try_again_timer = 10

    def debug(self, message):
        if self.debug_enabled:
            print message

    def mandate_for_legislator(self, legislator, party):
        try:
            mandate = Mandate.objects.get(legislator=legislator, date_start=self.legislature.date_start)
        except Mandate.DoesNotExist:
            mandate = Mandate(legislator=legislator, date_start=self.legislature.date_start, party=party,
                              legislature=self.legislature)
            mandate.save()
            self.debug("Mandate starting on %s did not exist, created." % self.legislature.date_start.strftime("%F"))
        return mandate

    def update_legislators(self):
        raise Exception("Not implemented.")

    def create_collection_run(self, legislature):
        collection_run, created = CollectionRun.objects.get_or_create(date=date.today(),
                                                                      legislature=legislature)
        self.collection_runs.append(collection_run)

        # Keep only one run for a day. If one exists, we delete the existing collection data
        # before we start this one.
        if not created:
            self.debug("Collection run for %s already exists for legislature %s, clearing." % (date.today().strftime("%F"), legislature))
            ArchivedExpense.objects.filter(collection_run=collection_run).delete()

        return collection_run

    def update_data(self):
        self.collection_run = self.create_collection_run(self.legislature)
        for mandate in Mandate.objects.filter(date_start__year=self.legislature.date_start.year,
                                              legislature=self.legislature):
            for year in range(self.legislature.date_start.year, datetime.now().year + 1):
                self.update_data_for_year(mandate, year)

    def retrieve_uri(self, uri, data=None, headers=None, post_process=True):
        retries = 0

        while retries < self.max_tries:
            try:
                r = requests.get(uri, data=data, headers=headers,
                                 timeout=self.default_timeout)
                if r.status_code == requests.codes.not_found:
                    return False
                if post_process:
                    return self.post_process_uri(r.text)
                else:
                    return r.text

            except requests.ConnectionError:
                retries += 1
                print "Unable to retrieve %s try(%d) - will try again in %d seconds." % (uri, retries, self.try_again_timer)

            time.sleep(self.try_again_timer)

        raise RuntimeError("Error: Unable to retrieve %s; Tried %d times." % (uri, self.max_tries))

    def post_process_uri(self, contents):
        return BeautifulSoup(contents, convertEntities=BeautifulStoneSoup.ALL_ENTITIES)
