/*
A KBase module: VirSorter
*/

module VirSorter {

    typedef string obj_ref

    typedef structure {
        string report_name;
        string report_ref;
        string workspace_name;
        obj_ref genomes;
        string database;
        obj_ref add_genomes;
        string virome;
        string diamond;
        string keep_db;
        string no_c;

    } InParams;

    funcdef run_VirSorter(InParams params)
        returns () authentication required;

};
