#!/bin/bash

MUSIC_DIR=/data/musik
DB=/data/mpi3/mpi3.db
SQLFILE=/tmp/mpi3._update.sql

IFS="
"

for f in `find ${MUSIC_DIR} -type d|tac`; do
        n=`echo "${f}" | sed -e 's/[^A-Za-z0-9._-/]/_/g'`
        if [[ "${f}" != "${n}" ]]; then
                if [[ ${1} == "-v" ]]; then echo $n; fi
                mv "$f" "$n"
        fi
done

echo "UPDATE songs SET found=0;" >${SQLFILE}
for f in `find ${MUSIC_DIR} -type f -name "*.mp3" -o -name "*.flac"`; do
        n=`echo "${f}" | sed -e 's/[^A-Za-z0-9._-/]/_/g'`
        if [[ "${f}" != "${n}" ]]; then
                if [[ ${1} == "-v" ]]; then echo $n; fi
                mv "$f" "$n"
        fi
        #echo "INSERT INTO songs (filename,found) VALUES('${n}',1) ON DUPLICATE KEY UPDATE found=1;" >> ${SQLFILE}
        echo "INSERT OR IGNORE INTO songs (filename,found) VALUES('${n}',1);" >> ${SQLFILE}
        echo "UPDATE SONGS SET found=1 WHERE filename LIKE '${n}';" >> ${SQLFILE}

done

echo "DELETE FROM disabled_songs WHERE sid IN (SELECT sid FROM songs WHERE found=0);" >> ${SQLFILE}
echo "DELETE FROM songs WHERE found=0;" >> ${SQLFILE}
sqlite3 ${DB} <${SQLFILE}
rm ${SQLFILE}
