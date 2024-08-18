import json
import waitress
import argparse
from flask import Flask
from flask import request
import sqlalchemy
import logging
import sqlalchemy.orm as orm
import sqlalchemy_utils
import flask

def makebase(path="portsmith.db"):
    if not dbexists(path):
        engine = sqlalchemy.create_engine(f"sqlite:///{path}")
        sqlalchemy_utils.create_database(engine.url)
        ORMBaseClass.metadata.create_all(engine)

def dbexists(path="portsmith.db"):
    engine = sqlalchemy.create_engine(f"sqlite:///{path}")
    return sqlalchemy_utils.database_exists(engine.url)

class ORMBaseClass(orm.DeclarativeBase):
    pass

class Ports(ORMBaseClass):
    __tablename__ = "ports"
    port:orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer, primary_key=True, autoincrement=False, nullable=False)

class Tags(ORMBaseClass):
    __tablename__ = "tags"
    key: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer,primary_key=True, autoincrement=True, nullable=False)
    port: orm.Mapped[int] = orm.mapped_column(sqlalchemy.ForeignKey("ports.port"), nullable=False)
    tag: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String, nullable=False)

class Properties(ORMBaseClass):
    __tablename__ = "properties"
    key: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer, primary_key=True, autoincrement=True, nullable=False)
    port: orm.Mapped[int] = orm.mapped_column(sqlalchemy.ForeignKey("ports.port"), nullable=False)
    name: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String, nullable=False)
    value: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String, nullable=False)

class Portsmith:
    def __init__(self, dbpath="portsmith.db"):
        self.engine=sqlalchemy.create_engine(f"sqlite:///{dbpath}")
        self.app=Flask(__name__)
        self.app.route("/reserved/<int:port>", methods=['GET', "POST", "PUT", "DELETE", "PATCH"])(self.reserved)
        self.app.route("/get_unreserved")(self.getNextUnreservedPort)
        self.app.route("/reserve_next", methods=['POST'])(self.reserveNextUnreservedPort)
        self.app.route("/discover", methods=['GET'])(self.discover)
        self.app.route("/ping", methods=['GET'])(self.ping)

    # Manage port reservations
    def reserved(self, port):
        if request.method=='GET':
            #check if port exists
            exists=self.doesPortExist(port)
            if not exists:
                return flask.Response("Port not reserved", 404)
        elif request.method=="POST":
            # check if port exists
            if self.doesPortExist(port):
                return flask.Response("Port already reserved", 409)
            # {"properties":{}, "tags":[]}
            if request.is_json:
                data = request.json
            else:
                data = {}
            self.reservePort(port, data)
            return flask.Response("Port reserved", 201)
        elif request.method=="PUT":
            #check if port exists
            exists = self.doesPortExist(port)
            if not exists:
                return flask.Response("Port not reserved", 404)
            data = request.json
            self.clearPort(port)
            self.reservePort(port, data)
            return flask.Response("Port reservation changed", 200)
        elif request.method=="DELETE":
            exists = self.doesPortExist(port)
            if not exists:
                return flask.Response("Port not reserved", 404)
            self.clearPort(port)
            return flask.Response("Port reservation cleared", 200)
        elif request.method=="PATCH":
            # {"properties":{}, "tags":{"removed":[], "added":[]}}
            exists = self.doesPortExist(port)
            if not exists:
                return flask.Response("Port not reserved", 404)
            data=request.json
            with orm.Session(self.engine) as session:
                if "properties" in data.keys():
                    for key in data['properties']:
                        value=data['properties'][key]
                        if value is None:
                            #delete value
                            delete_property = sqlalchemy.Delete(Properties).where(Properties.port == port, Properties.name==key)
                            session.execute(delete_property)
                        else:
                            check_property = sqlalchemy.Select(Properties).where(Properties.port==port, Properties.name==key)
                            if session.scalar(check_property) is None:
                                add_property = Properties(name=key, value=value, port=port)
                                session.add(add_property)
                            else:
                                update = sqlalchemy.Update(Properties).where(Properties.port==port, Properties.name==key).values(value=value)
                                session.execute(update)
                if 'tags' in data.keys():
                    tagchanges=data['tags']
                    if "removed" in tagchanges.keys():
                        for i in tagchanges['removed']:
                            delete_tag = sqlalchemy.Delete(Tags).where(Tags.tag==i, Tags.port==port)
                            session.execute(delete_tag)
                    if "added" in tagchanges.keys():
                        for i in tagchanges['added']:
                            add_tag = Tags(tag=i, port=port)
                            session.add(add_tag)
                session.commit()

            return flask.Response("Port reservation changed", 200)

    def ping(self):
        return "ok"

    def getNextUnreservedPort(self, internal=False):
        with orm.Session(self.engine) as session:
            ports=session.scalars(
                sqlalchemy.Select(Ports)
            )
            ports=[i.port for i in ports]

        nextport=55001
        ports.sort()
        for i in ports:
            if i==nextport:
                nextport+=1
            else:
                break
        if internal:
            return nextport
        else:
            return flask.Response(json.dumps({"port": nextport}), 200)

    def reserveNextUnreservedPort(self):
        port=self.getNextUnreservedPort(True)
        if request.is_json:
            data=request.json
        else:
            data={}
        self.reservePort(port, data)
        return flask.Response(json.dumps({"port": port}), 201)

    def discover(self):
        with orm.Session(self.engine) as session:
            ports=list(session.scalars(sqlalchemy.Select(Ports)))
        portmap={
            port.port:list(session.scalars(sqlalchemy.Select(Tags).where(Tags.port==port.port))) for port in ports
        }
        if 'tag' in request.args.keys():
            ports=self.getByTags(request.args.getlist('tag'))
        else:
            with orm.Session(self.engine) as session:
                ports=list(session.execute(sqlalchemy.Select(Ports.port)))
        ports=[i[0] for i in ports]
        if not ('detailed' in request.args.keys() and request.args['detailed'][0]=='1'):
            return ports

        portdata={

        }
        for port in ports:
            tags=[i[0] for i in session.execute(sqlalchemy.Select(Tags.tag).where(Tags.port==port))]
            properties={
                i[0]:i[1] for i in session.execute(sqlalchemy.Select(Properties.name, Properties.value).where(Properties.port==port))
            }
            portdata.update(
                {
                    port:{
                        "tags":tags,
                        "properties":properties
                    }
                }
            )
        return {
            "ports": ports,
            "detailed":portdata
        }


    def clearPort(self, port):
        with orm.Session(self.engine) as session:
            delete_properties=sqlalchemy.Delete(Properties).where(Properties.port == port)
            delete_tags = sqlalchemy.Delete(Tags).where(Tags.port == port)
            delete_port = sqlalchemy.Delete(Ports).where(Ports.port == port)
            session.execute(delete_properties)
            session.execute(delete_tags)
            session.execute(delete_port)
            session.commit()

    def reservePort(self, port, portData):
        with orm.Session(self.engine) as session:
            reserve_port = Ports(port=port)
            session.add(reserve_port)
            if "properties" in portData.keys():
                for i in portData['properties']:
                    property = Properties(port=port, name=i, value=portData['properties'][i])
                    session.add((property))
            if 'tags' in portData.keys():
                for tag in portData['tags']:
                    tagc = Tags(port=port, tag=tag)
                    session.add(tagc)

            session.commit()

    def doesPortExist(self, port):
        with orm.Session(self.engine) as session:
            selection = sqlalchemy.select(Ports).where(Ports.port == port)
            return session.scalar(selection) is not None

    def getByTags(self, tags):
        with orm.Session(self.engine) as session:
            wrapper = 'select port from ports as p where exists '
            needed = [
                f'(select port from tags where tag = :v{k} and p.port = port)' for k in range(len(tags))
            ]
            collected = wrapper + " and ".join(needed)
            repls = {
                f"v{k}": v for k, v in enumerate(tags)
            }

            return list(session.execute(sqlalchemy.text(collected), repls))

    def start(self, log_level=None):
        if log_level is not None:
            levelmap = {
                'critical': 50,
                'error': 40,
                'warning': 30,
                'info': 20,
                'debug': 10
            }
            logger = logging.getLogger('waitress')
            logger.setLevel(levelmap[log_level])

        waitress.serve(self.app, port=55000)

if __name__=="__main__":
    parser=argparse.ArgumentParser('portsmith.py', description="Basic controls for portsmith")
    subp=parser.add_subparsers(dest="action")
    startp=subp.add_parser("start")
    makep=subp.add_parser("create")
    startp.add_argument("--path", default="portsmith.db")
    startp.add_argument("--log-level", default="critical", choices=['critical', 'error', 'warning', 'info', 'debug'])

    makep.add_argument("--path", default="portsmith.db")

    args=parser.parse_args()
    if args.action=="create":
        if dbexists(args.path):
            print("DB already exists.")
            exit(1)
        makebase(args.path)
        print("DB created.")
        exit(0)
    elif args.action=="start":
        if not dbexists(args.path):
            print("DB does not exist.")
            exit(1)
        portsmith=Portsmith(args.path)
        portsmith.start(args.log_level)