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

    } ReportResults;

    /*
        This example function accepts any number of parameters and returns results in a KBaseReport
    */
    funcdef run_VirSorter(mapping<string,UnspecifiedObject> params) returns (ReportResults output) authentication required;

};
