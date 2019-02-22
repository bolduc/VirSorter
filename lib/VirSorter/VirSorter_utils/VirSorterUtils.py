import os
import subprocess
import time
import glob
import uuid
import tarfile
from string import Template
import pandas as pd
from pyparsing import Literal, SkipTo
import shutil
import csv
from Bio import SeqIO, SeqUtils


from installed_clients.AssemblyUtilClient import AssemblyUtil
from installed_clients.DataFileUtilClient import DataFileUtil as dfu
from installed_clients.KBaseReportClient import KBaseReport
from installed_clients.MetagenomeUtilsClient import MetagenomeUtils


html_template = Template("""<!DOCTYPE html>
<html lang="en">
  <head>
    <link href="https://netdna.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.10.19/css/jquery.dataTables.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/buttons/1.5.2/css/buttons.dataTables.min.css" rel="stylesheet">
    <script src="https://code.jquery.com/jquery-3.3.1.js" type="text/javascript"></script>
    <script src="https://cdn.datatables.net/1.10.19/js/jquery.dataTables.min.js" type="text/javascript"></script>
    <script src="https://cdn.datatables.net/buttons/1.5.2/js/dataTables.buttons.min.js" type="text/javascript"></script>
    <script src="https://cdn.datatables.net/buttons/1.5.2/js/buttons.html5.min.js" type="text/javascript"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.1.3/jszip.min.js" type="text/javascript"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.1.36/pdfmake.min.js" type="text/javascript"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.1.36/vfs_fonts.js" type="text/javascript"></script>

    <style>
    tfoot input {
        width: 100%;
        padding: 3px;
        box-sizing: border-box;
    }
    </style>

  </head>
  <body>
    <div class="container">
      <div>
        ${html_table}
      </div>
    </div>

    <script type="text/javascript">
      $$(document).ready(function() {
        $$('#my_id tfoot th').each( function () {
          var title = $$(this).text();
          $$(this).html( '<input type="text" placeholder="Search '+title+'" />' );
        });

        var table = $$('#my_id').DataTable({
          buttons: [
            'copyHtml5',
            'excelHtml5',
            'csvHtml5',
            'pdfHtml5'],
          scrollX: true,
          dom: 'Bfrtip'  //Necessary for buttons to work
        });

        table.columns().every( function () {
          var that = this;

          $$( 'input', this.footer() ).on( 'keyup change', function () {
            if ( that.search() !== this.value ) {
              that
              .search( this.value )
              .draw();
            }
          });
        } );
      } );
    </script>
  </body>
</html>""")


def log(message, prefix_newline=False):
    """
    Logging function, provides a hook to suppress or redirect log messages.
    """
    print(('\n' if prefix_newline else '') + '{0:.2f}'.format(time.time()) + ': ' + str(message))


class VirSorterUtils:

    def __init__(self, config):
        self.scratch = os.path.abspath(config['scratch'])
        self.callback_url = os.environ['SDK_CALLBACK_URL']
        self.mgu = MetagenomeUtils(self.callback_url)
        self.au = AssemblyUtil(self.callback_url)


    def VirSorter_help(self):
        command = 'wrapper_phage_contigs_sorter_iPlant.pl --help'
        self._run_command(command)

    def run_VirSorter(self, params):

        params['SDK_CALLBACK_URL'] = self.callback_url
        params['KB_AUTH_TOKEN'] = os.environ['KB_AUTH_TOKEN']

        # Get contigs from 'assembly'
        self.AssemblyUtil = AssemblyUtil(self.callback_url)
        genome_ret = self.AssemblyUtil.get_assembly_as_fasta({
            'ref': params['genomes']
        })

        genome_fp = genome_ret['path']

        command = 'wrapper_phage_contigs_sorter_iPlant.pl --data-dir /data/virsorter-data'

        # Add in first args
        command += ' -f {} --db {}'.format(genome_fp, params['database'])

        bool_args = ['virome', 'diamond', 'keep_db', 'no_c']  # keep_db = keep-db

        for bool_arg in bool_args:
            if params[bool_arg] == 1:  # 0 is true and therefore run
                if bool_arg == 'keep_db':
                    bool_arg = 'keep-db'

                command += ' --{}'.format(bool_arg)

        self._run_command(command)

        report = self._generate_report(params)

        return report

    def _run_command(self, command):
        """

        :param command:
        :return:
        """

        log('Start executing command:\n{}'.format(command))
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        output = pipe.communicate()[0]
        exitCode = pipe.returncode

        if (exitCode == 0):
            log('Executed command:\n{}\n'.format(command) +
                'Exit Code: {}\nOutput:\n{}'.format(exitCode, output))
        else:
            error_msg = 'Error running command:\n{}\n'.format(command)
            error_msg += 'Exit Code: {}Output:\n{}'.format(exitCode, output)

    def _parse_summary(self, virsorter_global_fp):
        columns = ['Contig_id', 'Nb genes contigs', 'Fragment', 'Nb genes', 'Category', 'Nb phage hallmark genes',
                   'Phage gene enrichment sig', 'Non-Caudovirales phage gene enrichment sig', 'Pfam depletion sig',
                   'Uncharacterized enrichment sig', 'Strand switch depletion sig', 'Short genes enrichment sig',
                   ]

        with open(virsorter_global_fp, 'r') as vir_fh:
            data = {}
            category = ''
            for line in vir_fh:
                if line.startswith('## Contig_id'):
                    continue
                elif line.startswith('## '):  # If 'header' lines are consumed by 1st if, then remaining should be good
                    category = line.split('## ')[-1].split(' -')[0]
                else:
                    values = line.strip().split(',')
                    data[values[0]] = dict(zip(columns[1:], values[1:]))

        df = pd.DataFrame().from_dict(data, orient='index')
        df.index.name = columns[0]
        df.reset_index(inplace=True)

        html = df.to_html(index=False, classes='my_class table-striped" id = "my_id')

        # Need to file write below
        direct_html = html_template.substitute(html_table=html)

        # Find header so it can be copied to footer, as dataframe.to_html doesn't include footer
        start_header = Literal("<thead>")
        end_header = Literal("</thead>")

        text = start_header + SkipTo(end_header)

        new_text = ''
        for data, start_pos, end_pos in text.scanString(direct_html):
            new_text = ''.join(data).replace(' style="text-align: right;"', '').replace('thead>',
                                                                                        'tfoot>\n  ') + '\n</tfoot>'

        # Get start and end positions to insert new text
        end_tbody = Literal("</tbody>")
        end_table = Literal("</table>")

        insertion_pos = end_tbody + SkipTo(end_table)

        final_html = ''
        for data, start_pos, end_pos in insertion_pos.scanString(direct_html):
            final_html = direct_html[:start_pos + 8] + '\n' + new_text + direct_html[start_pos + 8:]

        return final_html

    def _generate_report(self, params):
        """

        :param params:
        :return:
        """

        # Get URL
        self.dfu = dfu(params['SDK_CALLBACK_URL'])

        # Output directory should be $PWD/virsorter-out
        virsorter_outdir = os.path.join(os.getcwd(), 'virsorter-out')

        # kb_deseq functions out adding output files, then building report files, then sending all of them
        # to the workspace
        output_files = []  # Appended list of dicts containing attributes

        # Collect all the files needed to report to end-user
        # Get all predicted viral sequences
        pred_fnas = glob.glob(os.path.join(virsorter_outdir, 'Predicted_viral_sequences/VIRSorter_*.fasta'))
        pred_gbs = glob.glob(os.path.join(virsorter_outdir, 'Predicted_viral_sequences/VIRSorter_*.gb'))
        # Summary 'table'
        glob_signal = os.path.join(virsorter_outdir, 'VIRSorter_global-phage-signal.csv')

        # ...
        output_dir = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(output_dir)

        # Deal with nucleotide fasta
        pred_fna_tgz_fp = os.path.join(output_dir, 'VIRSorter_predicted_viral_fna.tar.gz')
        with tarfile.open(pred_fna_tgz_fp, 'w:gz') as pred_fna_tgz_fh:
            for pred_fna in pred_fnas:
                pred_fna_tgz_fh.add(pred_fna, arcname=os.path.basename(pred_fna))
        output_files.append({
            'path': pred_fna_tgz_fp,
            'name': os.path.basename(pred_fna_tgz_fp),
            'label': os.path.basename(pred_fna_tgz_fp),
            'description': 'FASTA-formatted nucleotide sequences of VIRSorter predicted phage'
        })

        pred_gb_tgz_fp = os.path.join(output_dir, 'VIRSorter_predicted_viral_gb.tar.gz')
        with tarfile.open(pred_gb_tgz_fp, 'w:gz') as pred_gb_tgz_fh:
            for pred_gb in pred_gbs:
                pred_gb_tgz_fh.add(pred_gb, arcname=os.path.basename(pred_gb))
        output_files.append({
            'path': pred_gb_tgz_fp,
            'name': os.path.basename(pred_gb_tgz_fp),
            'label': os.path.basename(pred_gb_tgz_fp),
            'description': 'Genbank-formatted sequences of VIRSorter predicted phage'
        })

        # Before creating final HTML output, need to create BinnedContig object so other tools/users can take advantage
        # of its features, but also to feed more easily into other tools (e.g. vConTACT)
        created_objects = []
        for category_fp in pred_fnas:
            category = os.path.basename(category_fp).split('cat-')[-1].split('.')[0]
            dest_fn = 'VirSorter.{}.fasta'.format(category.zfill(3))
            dest_fp = os.path.join(output_dir, dest_fn)

            genome_size = 0
            gc_content = []

            with open(category_fp, 'rU') as category_fh:
                for record in SeqIO.parse(category_fh, 'fasta'):
                    seq = record.seq
                    gc_content.append(SeqUtils.GC(seq))
                    genome_size += len(seq)

            if genome_size != 0:  # Empty file

                shutil.copyfile(category_fp, dest_fp)

                result = self.au.save_assembly_from_fasta(
                    {'file': {'path': dest_fp},
                     'workspace_name': params['workspace_name'],
                     'assembly_name': 'VirSorter-Category-{}'.format(category)
                     })

                created_objects.append({"ref": result,
                                        "description": "AssembliedContigs from VIRSorter"})

        # Now have a "max_bin" directory

        # But before finishing up max_bin stuff, need to make an assembly object so there's an assembly ref to use

        # Use global signal (i.e. summary) file and create HTML-formatted version
        raw_html = self._parse_summary(glob_signal)

        html_fp = os.path.join(output_dir, 'index.html')

        with open(html_fp, 'w') as html_fh:
            html_fh.write(raw_html)

        report_shock_id = self.dfu.file_to_shock({
            'file_path': output_dir,
            'pack': 'zip'
        })['shock_id']

        html_report = [{
            'shock_id': report_shock_id,
            'name': os.path.basename(html_fp),
            'label': os.path.basename(html_fp),
            'description': 'HTML summary report for VIRSorter'
        }]

        report_params = {'message': 'Basic message to show in the report',
                         'workspace_name': params['workspace_name'],
                         'html_links': html_report,
                         'direct_html_link_index': 0,
                         'report_object_name': 'VIRSorter_report_{}'.format(str(uuid.uuid4())),
                         'file_links': output_files,
                         # Don't use until data objects that are created as result of running app
                         # 'objects_created': [{'ref': created_objects,
                         #                      'description': 'Fix this before publication'}],
                         'objects_created': created_objects,
                         }

        kbase_report_client = KBaseReport(params['SDK_CALLBACK_URL'], token=params['KB_AUTH_TOKEN'])
        output = kbase_report_client.create_extended_report(report_params)

        report_output = {'report_name': output['name'], 'report_ref': output['ref']}

        return report_output

    def _mkdir_p(self, path):
        """
        :param path:
        :return:
        """

        if not path:
            return
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise
