# -*- coding: utf-8 -*-
#BEGIN_HEADER
import os
from installed_clients.KBaseReportClient import KBaseReport
from VirSorter.VirSorter_utils.VirSorterUtils import VirSorterUtils
#END_HEADER


class VirSorter:
    '''
    Module Name:
    VirSorter

    Module Description:
    A KBase module: VirSorter
    '''

    ######## WARNING FOR GEVENT USERS ####### noqa
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    ######################################### noqa
    VERSION = "0.0.1"
    GIT_URL = ""
    GIT_COMMIT_HASH = ""

    #BEGIN_CLASS_HEADER
    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.callback_url = os.environ['SDK_CALLBACK_URL']
        self.shared_folder = config['scratch']
        #END_CONSTRUCTOR
        pass


    def run_VirSorter(self, ctx, params):
        """
        This example function accepts any number of parameters and returns results in a KBaseReport
        :param params: instance of mapping from String to unspecified object
        :returns: instance of type "ReportResults" -> structure: parameter
           "report_name" of String, parameter "report_ref" of String
        """
        # ctx is the context object
        # return variables are: output
        #BEGIN run_VirSorter

        self.callback_url = os.environ['SDK_CALLBACK_URL']
        params['SDK_CALLBACK_URL'] = self.callback_url
        params['KB_AUTH_TOKEN'] = os.environ['KB_AUTH_TOKEN']

        vc = VirSorterUtils(self.config)

        # report = KBaseReport(self.callback_url)
        # report_info = report.create({'report': {'objects_created':[],
        #                                         'text_message': params['parameter_1']},
        #                                         'workspace_name': params['workspace_name']})
        # output = {
        #     'report_name': report_info['name'],
        #     'report_ref': report_info['ref'],
        # }
        returnVal = vc.run_VirSorter(params)  # Output
        return returnVal

        #END run_VirSorter

        # At some point might do deeper type checking...
        # if not isinstance(output, dict):
        #     raise ValueError('Method run_VirSorter return value ' +
        #                      'output is not type dict as required.')
        # return the results
        # return [output]
    def status(self, ctx):
        #BEGIN_STATUS
        returnVal = {'state': "OK",
                     'message': "",
                     'version': self.VERSION,
                     'git_url': self.GIT_URL,
                     'git_commit_hash': self.GIT_COMMIT_HASH}
        #END_STATUS
        return [returnVal]
