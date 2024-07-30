import base64
import importlib
import json
from typing import Dict

import httpx
import psycopg2
import mysql.connector
from elasticsearch import Elasticsearch
from pymongo import MongoClient

from .generated.about import About
from .generated.execute import Execute
from .generated.execute_connection import ExecuteConnection
from .generated.response import Response
from .generated.response_event import ResponseEvent
from .generated.response_http import ResponseHTTP
from .generated.response_log import ResponseLog


class Runtime:
    def get(self):
        about = About()
        about.api_version = "1.0.0"
        about.language = "python"
        return about

    def run(self, action: str, execute: Execute):
        connector = Connector(execute.connections)
        dispatcher = Dispatcher()
        logger = Logger()
        response_builder = ResponseBuilder()

        module = importlib.import_module(action, package=__name__)

        module.handle(execute.request, execute.context, connector, response_builder, dispatcher, logger)

        response = response_builder.get_response()
        if not response:
            response = ResponseHTTP()
            response.status_code = 204

        result = Response()
        result.response = response
        result.events = dispatcher.get_events()
        result.logs = logger.get_logs()
        return result


class Connector:
    def __init__(self, configs: Dict[str, ExecuteConnection]):
        self.configs = configs
        self.connections = {}

    def get_connection(self, name):
        if name in self.connections.keys():
            return self.connections[name]

        if name not in self.configs.keys():
            raise Exception("Provided connection is not configured")

        connection = self.configs[name]
        config = json.loads(base64.b64decode(connection.config))

        if connection.type == "Fusio.Adapter.Sql.Connection.Sql":
            if config['type'] == "pdo_mysql":
                con = mysql.connector.connect(
                    host=config['host'],
                    user=config['username'],
                    password=config['password'],
                    database=config['database']
                )
            elif config['type'] == "pdo_pgsql":
                con = psycopg2.connect(
                    host=config['host'],
                    user=config['username'],
                    password=config['password'],
                    database=config['database']
                )
            else:
                raise Exception("SQL type is not supported")

            self.connections[name] = con

            return con
        elif connection.type == "Fusio.Adapter.Sql.Connection.SqlAdvanced":
            # TODO

            return None
        elif connection.type == "Fusio.Adapter.Http.Connection.Http":
            client = httpx.Client(base_url=config['url'])

            # @TODO configure proxy for http client
            # config['username']
            # config['password']
            # config['proxy']

            self.connections[name] = client

            return client
        elif connection.type == "Fusio.Adapter.Mongodb.Connection.MongoDB":
            client = MongoClient(config['url'])
            database = client[config['database']]

            self.connections[name] = database

            return database
        elif connection.type == "Fusio.Adapter.Elasticsearch.Connection.Elasticsearch":
            host = config['host']
            client = Elasticsearch(host.split(','))

            self.connections[name] = client

            return client
        else:
            raise Exception("Provided a not supported connection type")


class Dispatcher:
    def __init__(self):
        self.events = []

    def dispatch(self, event_name, data):
        event = ResponseEvent()
        event.event_name = event_name
        event.data = data
        self.events.append(event)

    def get_events(self):
        return self.events


class Logger:
    def __init__(self):
        self.logs = []

    def emergency(self, message):
        self.log("EMERGENCY", message)

    def alert(self, message):
        self.log("ALERT", message)

    def critical(self, message):
        self.log("CRITICAL", message)

    def error(self, message):
        self.log("ERROR", message)

    def warning(self, message):
        self.log("WARNING", message)

    def notice(self, message):
        self.log("NOTICE", message)

    def info(self, message):
        self.log("INFO", message)

    def debug(self, message):
        self.log("DEBUG", message)

    def log(self, level, message):
        log = ResponseLog()
        log.level = level
        log.message = message
        self.logs.append(log)

    def get_logs(self):
        return self.logs


class ResponseBuilder:
    def __init__(self):
        self.response = None

    def build(self, status_code, headers, body):
        self.response = ResponseHTTP()
        self.response.status_code = status_code
        self.response.headers = headers
        self.response.body = body

    def get_response(self):
        return self.response
