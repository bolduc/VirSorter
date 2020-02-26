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
from installed_clients.WorkspaceClient import Workspace


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
        self.ws = Workspace(config['workspace-url'], token=config['token'])

    def VirSorter_help(self):
        command = 'wrapper_phage_contigs_sorter_iPlant.pl --help'
        self._run_command(command)

    def get_fasta(self, ref):
        # check type of object, i.e KBaseGenomeAnnotations.Assembly-3.0
        obj_type = self.ws.get_object_info3({'objects': [{'ref': ref}]})['infos'][0][2]
        if 'assembly' in obj_type.lower():
            genome_ref = ref
        elif 'kbasegenomes' in obj_type.lower():
            data = self.ws.get_objects2({'objects': [
                {'ref': ref, 'included': ['assembly_ref'], 'strict_maps': 1}]})['data'][0]['data']
            genome_ref = data['assembly_ref']
        else:
            raise ValueError(f"Input reference {ref} is of type {obj_type}. Type KBaseGenomes.Genome or "
                             f"KBaseGenomeAnnotations.Assembly required.")
        return self.au.get_assembly_as_fasta({'ref': genome_ref})['path']

    def run_VirSorter(self, params):

        params['SDK_CALLBACK_URL'] = self.callback_url
        params['KB_AUTH_TOKEN'] = os.environ['KB_AUTH_TOKEN']

        # Get contigs from 'assembly'
        genome_fp = self.get_fasta(params['genomes'])

        command = 'wrapper_phage_contigs_sorter_iPlant.pl --data-dir /data/virsorter-data'

        # Add in first args
        command += f' -f {genome_fp} --db {params["database"]}'

        # Check if additional genomes were submitted
        if params.get('add_genomes'):
            add_genomes_fp = self.get_fasta(params['add_genomes'])
            print(f'Added genomes DETECTED: {add_genomes_fp}')
            command += f' --cp {add_genomes_fp}'

        bool_args = ['virome', 'diamond', 'keep_db', 'no_c']  # keep_db = keep-db

        for bool_arg in bool_args:
            if params[bool_arg] == 1:  # 0 is true and therefore run... though for some reason it's reversed on json
                if bool_arg == 'keep_db':
                    bool_arg = 'keep-db'

                command += f' --{bool_arg}'

        self._run_command(command)

        report = self._generate_report(params)  # Basically, do everything that's after the tool runs

        return report

    def _run_command(self, command):
        """

        :param command:
        :return:
        """

        log('Start executing command:\n{}'.format(command))
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        output, err = pipe.communicate()
        exitCode = pipe.returncode

        if exitCode == 0:
            log('Executed command:\n{}\n'.format(command) +
                'Exit Code: {}\nOutput:\n{}'.format(exitCode, output))
        else:
            error_msg = 'Error running command:\n{}\n'.format(command)
            error_msg += 'Exit Code: {}\nOutput:\n{}\nError: {}'.format(exitCode, output, err)
            raise RuntimeError(error_msg)

    def _parse_summary(self, virsorter_global_fp):
        columns = ['Contig_id', 'Nb genes contigs', 'Fragment', 'Nb genes', 'Category', 'Nb phage hallmark genes',
                   'Phage gene enrichment sig', 'Non-Caudovirales phage gene enrichment sig', 'Pfam depletion sig',
                   'Uncharacterized enrichment sig', 'Strand switch depletion sig', 'Short genes enrichment sig',
                   ]

        try:
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
        except:
            vir_path = os.path.join(os.getcwd(), 'virsorter-out')
            files = os.listdir(vir_path)
            raise RuntimeError(f"{virsorter_global_fp} is not a file. existing files {files}.")

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

    def get_assembly_contig_ids(self, assembly_ref):
        """get contig ids from assembly_ref"""
        contigs = self.ws.get_objects2({'objects': [{'ref': assembly_ref, 'included': ['contigs']}]})['data'][0]['data']['contigs']
        return contigs.keys()

    def _generate_report(self, params):
        """

        :param params:
        :return:
        """

        # Get URL
        self.dfu = dfu(params['SDK_CALLBACK_URL'])

        # Output directory should be $PWD/virsorter-out - ASSUMES that's the output location
        virsorter_outdir = os.path.join(os.getcwd(), 'virsorter-out')

        print(f'VIRSorter output directory contents: {os.listdir(virsorter_outdir)}')

        # Replacing individual download files with BinnedContigs

        # kb_deseq adds output files, then builds report files and sends all of them to the workspace
        output_files = []  # Appended list of dicts containing attributes

        # Collect all the files needed to report to end-user
        # Get all predicted viral sequences
        pred_fnas = glob.glob(os.path.join(virsorter_outdir, 'Predicted_viral_sequences/VIRSorter_*.fasta'))
        pred_gbs = glob.glob(os.path.join(virsorter_outdir, 'Predicted_viral_sequences/VIRSorter_*.gb'))
        # Summary 'table'
        glob_signal = os.path.join(virsorter_outdir, 'VIRSorter_global-phage-signal.csv')

        print('Identified the following predicted viral sequences:\n{}'.format('\n\t'.join(pred_fnas)))

        if len(pred_fnas) == 0:
            print(f"Unable to find predicted viral sequences, here are the directory's content:\n"
                  f"{os.listdir(os.path.join(virsorter_outdir, 'Predicted_viral_sequences'))}")

        if os.path.exists(glob_signal):

            print(f'Identified the global phage signal: {glob_signal}')

            lines = -1  # Don't count header
            with open(glob_signal) as fh:
                for ln in fh:
                    lines += 1

            if lines == 0:
                print('But it is EMPTY!')

        else:
            print('Unable to find the global phage signal file. Was there an error during the run?')

        # Append error and out files from VIRSorter
        err_fp = os.path.join(virsorter_outdir, 'logs/err')
        # if os.path.exists(err_fp):
        #     output_files.append({
        #         'path': os.path.join(virsorter_outdir, 'logs/err'),
        #         'name': 'VIRSorter_err',
        #         'label': 'VIRSorter_err',
        #         'description': 'VIRSorter error log file, generated from the tool itself.'
        #     })
        out_fp = os.path.join(virsorter_outdir, 'logs/out')
        # if os.path.exists(out_fp):
        #     output_files.append({
        #         'path': os.path.join(virsorter_outdir, 'logs/out'),
        #         'name': 'VIRSorter_out',
        #         'label': 'VIRSorter_out',
        #         'description': 'VIRSorter output log file, generated from the tool itself.'
        #     })

        if not (os.path.exists(err_fp) or os.path.exists(out_fp)):
            print('Unable to find err and/or out files in LOG directory, contents:')
            print(os.listdir(os.path.join(virsorter_outdir, 'logs')))

        # Make output directory
        output_dir = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(output_dir)

        # Deal with nucleotide and protein fasta
        pred_fna_tgz_fp = os.path.join(output_dir, 'VIRSorter_predicted_viral_fna.tar.gz')
        with tarfile.open(pred_fna_tgz_fp, 'w:gz') as pred_fna_tgz_fh:  # Compress to minimize disk usage
            for pred_fna in pred_fnas:
                pred_fna_tgz_fh.add(pred_fna, arcname=os.path.basename(pred_fna))
        output_files.append({
            'path': pred_fna_tgz_fp,
            'name': os.path.basename(pred_fna_tgz_fp),
            'label': os.path.basename(pred_fna_tgz_fp),
            'description': 'FASTA-formatted nucleotide sequences of VIRSorter predicted viruses'
        })

        if os.path.exists(pred_fna_tgz_fp):
            print(f'Generated gzipped version of the predicted viral sequences in FASTA format: '
                  f'{pred_fna_tgz_fp}')

        pred_gb_tgz_fp = os.path.join(output_dir, 'VIRSorter_predicted_viral_gb.tar.gz')
        with tarfile.open(pred_gb_tgz_fp, 'w:gz') as pred_gb_tgz_fh:
            for pred_gb in pred_gbs:
                pred_gb_tgz_fh.add(pred_gb, arcname=os.path.basename(pred_gb))
        output_files.append({
            'path': pred_gb_tgz_fp,
            'name': os.path.basename(pred_gb_tgz_fp),
            'label': os.path.basename(pred_gb_tgz_fp),
            'description': 'Genbank-formatted sequences of VIRSorter predicted viruses'
        })

        if os.path.exists(pred_gb_tgz_fp):
            print(f'Generated gzipped version of the predicted viral sequences in Genbank format: '
                  f'{pred_gb_tgz_fp}')

        # To create BinnedContig, need to create another directory with each of the "bins" as separate files?
        binned_contig_output_dir = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(binned_contig_output_dir)

        # Before creating final HTML output, need to create BinnedContig object so other tools/users can take advantage
        # of its features, but also to feed more easily into other tools (e.g. vConTACT)
        created_objects = []  # Will store the objects that go to the workspace

        # load contig ids from the assembly input
        # assembly_contig_ids = self.get_assembly_contig_ids(self.assembly_ref)
        assembly_contig_ids = self.get_assembly_contig_ids(params['genomes'])  # Will fail for Genome

        summary_fp = os.path.join(binned_contig_output_dir, 'VIRSorter.summary')  # Anything that ends in .summary
        with open(summary_fp, 'w') as summary_fh:

            summary_writer = csv.writer(summary_fh, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
            summary_writer.writerow(['Bin name', 'Completeness', 'Genome size', 'GC content'])

            for category_fp in pred_fnas:
                # _get_bin_ids from MetaGenomeUtils requires files to follow the header.0xx.fasta convention
                category = os.path.basename(category_fp).split('cat-')[-1].split('.')[0]
                dest_fn = 'VirSorter.{}.fasta'.format(category.zfill(3))
                dest_fp = os.path.join(output_dir, dest_fn)
                binned_contig_fp = os.path.join(binned_contig_output_dir, dest_fn)

                genome_size = 0
                gc_content = []

                # Need stats for summary file
                # Also need to adjust sequence name so binnedContig object can retrieve sequences
                adjusted_sequences = []
                with open(category_fp, 'rU') as category_fh:
                    for record in SeqIO.parse(category_fh, 'fasta'):
                        seq = record.seq
                        gc_content.append(SeqUtils.GC(seq))
                        genome_size += len(seq)

                        # This is very dirty, but need to change name to match original contigs
                        record.id = record.id.replace('VIRSorter_', '').replace('-circular', '').split('-cat_')[0]
                        if 'gene' in record.id:  # Prophage
                            record.id = record.id.split('_gene')[0]
                        record.id = record.id.rsplit('_', 1)[0]

                        # here we make sure that the id's line up with contig ids in the input assembly object
                        if record.id not in assembly_contig_ids:
                            for assembly_contig_id in assembly_contig_ids:
                                # first check if record.id is substring of current contig id,
                                # then check if current contig id is substring of record.id
                                # NOTE: this is not a perfect way of checking and will likely
                                #       fail in some circumstances.
                                #       A more complete check would be to make sure there is a 1:1
                                #       mapping of contig id's in the assembly object as compared to
                                #       the binned contig object (the fasta files defined here).
                                if (record.id in assembly_contig_id) or (assembly_contig_id in record.id):
                                    record.id = assembly_contig_id
                                    break

                        record.description = ''
                        record.name = ''
                        adjusted_sequences.append(record)

                if genome_size != 0:  # Empty file

                    summary_writer.writerow([dest_fn, '100%', genome_size, (sum(gc_content) / len(gc_content))])

                    print('Copying {} to results directory'.format(os.path.basename(category_fp)))
                    # Yes, need both. One is to get file_links in report. Second is for binnedContigs object
                    shutil.copyfile(category_fp, dest_fp)

                    # Write renamed sequences
                    with open(binned_contig_fp, 'w') as binned_contig_fh:
                        SeqIO.write(adjusted_sequences, binned_contig_fh, 'fasta')

                    result = self.au.save_assembly_from_fasta(
                        {'file': {'path': dest_fp},
                         'workspace_name': params['workspace_name'],
                         'assembly_name': 'VirSorter-Category-{}'.format(category)
                         })

                    created_objects.append({"ref": result,
                                            "description": "KBase Assembly object from VIRSorter"})

        # Create BinnedContigs object, but 1st, a little metadata
        generate_binned_contig_param = {
            'file_directory': binned_contig_output_dir,
            'assembly_ref': params['genomes'],  # params.get('genomes'), self.assembly_ref
            'binned_contig_name': params['binned_contig_name'],
            'workspace_name': params['workspace_name']
        }
        binned_contig_object_ref = self.mgu.file_to_binned_contigs(
            generate_binned_contig_param).get('binned_contig_obj_ref')

        # Add binned contigs reference here, as it was already created above
        created_objects.append({"ref": binned_contig_object_ref,
                                "description": "BinnedContigs from VIRSorter"})

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
            'description': 'HTML summary report for VIRSorter-predicted viral genomes.'
        }]

        report_params = {'message': 'Here are the results from your VIRSorter run. Above, you\'ll find a report with '
                                    'all the identified (putative) viral genomes, and below, links to the report as '
                                    'well as files generated.',
                         'workspace_name': params['workspace_name'],
                         'html_links': html_report,
                         'direct_html_link_index': 0,
                         'report_object_name': 'VIRSorter_report_{}'.format(str(uuid.uuid4())),
                         'file_links': output_files,
                         'objects_created': created_objects,
                         }

        kbase_report_client = KBaseReport(params['SDK_CALLBACK_URL'], token=params['KB_AUTH_TOKEN'])
        output = kbase_report_client.create_extended_report(report_params)

        report_output = {
            'report_name': output['name'],
            'report_ref': output['ref'],
            'result_directory': binned_contig_output_dir,
            'binned_contig_obj_ref': binned_contig_object_ref}

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
