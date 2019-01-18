#!/bin/bash

. /kb/deployment/user-env.sh

python ./scripts/prepare_deploy_cfg.py ./deploy.cfg ./work/config.properties

if [ -f ./work/token ] ; then
  export KB_AUTH_TOKEN=$(<./work/token)
fi

if [ $# -eq 0 ] ; then
  sh ./scripts/start_server.sh
elif [ "${1}" = "test" ] ; then
  echo "Run Tests"
  make test
elif [ "${1}" = "async" ] ; then
  sh ./scripts/run_async.sh
elif [ "${1}" = "init" ] ; then
  echo "Initialize module"
  cd /data/
  echo "Getting databases"
  curl -O https://zenodo.org/record/1168727/files/virsorter-data-v2.tar.gz
  tar zxf virsorter-data-v2.tar.gz
  rm -rf virsorter-data-v2.tar.gz

  if [[ -d "/data/virsorter-data" ]] ; then
    touch /data/__READY__
  else
    echo "init failed"
  fi

elif [ "${1}" = "bash" ] ; then
  bash
elif [ "${1}" = "report" ] ; then
  export KB_SDK_COMPILE_REPORT_FILE=./work/compile_report.json
  make compile
else
  echo Unknown
fi
