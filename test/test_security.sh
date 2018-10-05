#! /bin/bash

su -c "dynamo $PWD/hole.py" dynamo
echo "select * from sites" | mysql -ptest -Ddynamo | grep "INSERTED_SITE"

# We don't want the grep to succeed
if [ $? -eq 0 ]
then
    # Clear out
    echo "delete from sites" | mysql -ptest -Ddynamo
    exit 1
fi

exit 0
