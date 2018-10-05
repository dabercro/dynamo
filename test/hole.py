#! /usr/bin/env python

from dynamo import dataformat
from dynamo.core.executable import inventory


def main():

    for res in inventory._store._mysql.query("show grants;"):
        print res
    inventory._store._mysql.query(
        "insert into sites (name, storage_type, status) values ('INSERTED_SITE', 'disk', 'unknown');"
        )

if __name__ == '__main__':
    main()
