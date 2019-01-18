FROM kbase/sdkbase2:python
MAINTAINER KBase Developer
# -----------------------------------------
# In this section, you can install any system dependencies required
# to run your App.  For instance, you could place an apt-get update or
# install line here, a git checkout to download code, or run any other
# installation scripts.

## docker build -t bolduc/virsorter .
## docker run --rm -v $(pwd):/wdir -w /wdir bolduc/virsorter:latest -f Contigs.fasta -db 1 --ncpu 4 --data-dir /virsorter-data

## Prepare the environment variables
ENV PATH=/miniconda/bin:${PATH} PERL5LIB=/miniconda/lib/perl5/site_perl/5.22.0/:${PERL5LIB}

## Install dependencies
RUN apt-get update && apt-get install -y libdb-dev curl git build-essential openjdk-8-jdk

RUN curl -LO http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
	bash Miniconda3-latest-Linux-x86_64.sh -b -f -p /miniconda && \
	rm Miniconda3-latest-Linux-x86_64.sh

RUN conda update -y conda && \
  conda install -y -c bioconda mcl=14.137 muscle blast perl-bioperl perl-file-which hmmer=3.1b2 perl-parallel-forkmanager perl-list-moreutils diamond && \
  conda clean --yes --tarballs --packages --source-cache

RUN git clone https://github.com/simroux/VirSorter.git && \
  cd VirSorter/Scripts && make clean && make && \
  ln -s /VirSorter/wrapper_phage_contigs_sorter_iPlant.pl /usr/local/bin/ && \
  ln -s /VirSorter/Scripts /usr/local/bin/

RUN curl -LO http://metagene.nig.ac.jp/metagene/mga_x86_64.tar.gz && \
  tar -xvf mga_x86_64.tar.gz && mv mga_linux_ia64 /usr/local/bin/

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


# -----------------------------------------

COPY ./ /kb/module
RUN mkdir -p /kb/module/work
RUN chmod -R a+rw /kb/module

WORKDIR /kb/module

RUN make all

ENTRYPOINT [ "./scripts/entrypoint.sh" ]

CMD [ ]
