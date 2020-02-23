FROM kbase/sdkbase2:python
MAINTAINER KBase Developer
# -----------------------------------------
# In this section, you can install any system dependencies required
# to run your App.  For instance, you could place an apt-get update or
# install line here, a git checkout to download code, or run any other
# installation scripts.

## Prepare the environment variables
ENV PATH=/miniconda/bin:${PATH} PERL5LIB=/miniconda/lib/perl5/site_perl/5.22.0/:${PERL5LIB}

RUN echo "Start of Dockerbuild!"

## Install dependencies
RUN apt-get update && apt-get install -y libdb-dev curl git build-essential

RUN conda install -y -c bioconda mcl=14.137 muscle blast perl-bioperl perl-file-which hmmer=3.1b2 \
    perl-parallel-forkmanager perl-list-moreutils diamond pyparsing

## Keeping separate, although not very Docker-kosher, as these are packages not installed in base image???

RUN pip install jsonrpcbase pandas nose jinja2

#RUN conda clean --yes --tarballs --packages --source-cache
#RUN conda build purge-all
#RUN conda-build purge-all

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
