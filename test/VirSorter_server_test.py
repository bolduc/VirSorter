# -*- coding: utf-8 -*-
import os
import time
import unittest
from configparser import ConfigParser
from Bio import SeqIO

from VirSorter.VirSorterImpl import VirSorter
from VirSorter.VirSorterServer import MethodContext
from VirSorter.authclient import KBaseAuth as _KBaseAuth

from installed_clients.WorkspaceClient import Workspace
from installed_clients.AssemblyUtilClient import AssemblyUtil

class VirSorterTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = os.environ.get('KB_AUTH_TOKEN', None)
        config_file = os.environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('VirSorter'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'VirSorter',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = Workspace(cls.wsURL)
        cls.serviceImpl = VirSorter(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']
        cls.au = AssemblyUtil(cls.callback_url)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_VirSorter_" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})  # noqa
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def check_if_contig_ids_align(self, assembly_ref, binned_ref):
        """make sure all bin ids show up in assembly ids"""
        # 1.) get assembly object ids
        fasta_path = self.au.get_assembly_as_fasta({'ref': assembly_ref})['path']
        assembly_ids = []
        for record in SeqIO.parse(fasta_path, 'fasta'):
            assembly_ids.append(record.id)
        # 2.) get binned contig object ids
        binned_data = self.wsClient.get_objects2({'objects': [{'ref': binned_ref}]})['data'][0]['data']
        bin_ids = []
        for b in binned_data['bins']:
            bin_ids += b['contigs'].keys()
        # print("BINS")
        # print(bin_ids)
        # print('ASSEMBLY')
        # print(assembly_ids)
        for id_ in bin_ids:
            self.assertTrue(id_ in assembly_ids, msg=f"{id_} contig id in BinnedContig object could "
                                                     f"not be found in corresponding Assembly object.")

    # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa
    def test_your_method(self):
        # Prepare test objects in workspace if needed using
        # self.getWsClient().save_objects({'workspace': self.getWsName(),
        #                                  'objects': []})
        #
        # Run your method by
        # ret = self.getImpl().your_method(self.getContext(), parameters...)
        #
        # Check returned data with
        # self.assertEqual(ret[...], ...) or other unittest methods
        assembly_ref = "31160/20/1"
        added_genomes = "31160/45/1"
        ret = self.getImpl().run_VirSorter(self.getContext(), {
            'workspace_name': self.getWsName(),
            'genomes': assembly_ref,
            'add_genomes': added_genomes,
            'database': '1',
            'virome': '0',
            'diamond': '0',
            'keep_db': '1',
            'no_c': '0',
            'binned_contig_name': 'binnedContig'

        })[0]
        self.check_if_contig_ids_align(assembly_ref, ret['binned_contig_obj_ref'])
