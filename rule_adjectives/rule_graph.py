"""Tool to parse the rules tsv, and make a graph."""
import re
import os
import pandas as pd
import numpy as np
import networkx as nx
import graphviz
from rule_adjectives.annotations import Annotations

LEAF_NODES = ['ko', 'camper', 'fegenie', 'sulfur', 'PF', 'ec', 'columnvalue']

def parse_ands(logic:str):
    depth = 0
    for i, c in enumerate(logic):
        if c == "[":
            depth += 1
        if c == "]":
            depth -= 1
        if c == "&" and depth == 0:
            return parse_ands(logic[:i]) + parse_ands(logic[i+1:])
    return [logic]


def parse_ors(logic:str):
    depth = 0
    for i, c in enumerate(logic):
        if c == "[":
            depth += 1
        if c == "]":
            depth -= 1
        if c == "|" and depth == 0:
            return parse_ors(logic[:i]) + parse_ors(logic[i+1:])
    return [logic]


def parse_steps(logic:str):
    depth = 0
    for i, c in enumerate(logic):
        if c == "[":
            depth += 1
        if c == "]":
            depth -= 1
        if c == "," and depth == 0:
            return parse_steps(logic[:i]) + parse_steps(logic[i+1:])
    return [logic]


def test_steps():
    assert parse_steps("1,2,3,4|6")


def parse_functions(logic):
    if re.match(r'^percent:[0-9]+:[A-z,0-9]+$', logic):
        out = logic.split(':')
        name = out[0]
        args = out[1]
        kids = out[2]
        return name, args, kids
    if re.match(r'^not:[A-z,0-9]+$', logic):
        out = logic.split(':')
        name = out[0]
        args = None
        kids = out[1]
        return name, args, kids
    if re.match(r'^atleast:[0-9]+:[A-z,0-9]+$', logic):
        out = logic.split(':')
        name = out[0]
        args = out[1]
        kids = out[2]
        return name, args, kids
    if re.match(r'^inGenomeCount:[0-9]+:[A-z,0-9]+$', logic):
        out = logic.split(':')
        name = out[0]
        args = out[1]
        kids = out[2]
        return name, args, kids
    if re.match(r'^columnvalue:[A-z][A-z]:[A-z,0-9]+:[A-z,0-9]+$', logic):
        out = logic.split(':')
        name = out[0]
        args = {'comp':out[1], 'val':out[2], 'col':out[3]}
        kids = None
        return name, args, kids
    if re.match(r'^columncontains:[A-z,0-9]+:[A-z,0-9]+$', logic):
        out = logic.split(':')
        name = out[0]
        args = {'col':out[1], 'val':out[2]}
        kids = None
        return name, args, kids


def ec_func(ec:str, annotations):
    if re.match(r'-$', ec):
        ec = ec[:-1]
        return np.any([i.startswith(ec) for i in annotations])
    else:
        return ec in annotations


def ko_func(ko:str, annotations):
    return ko in annotations


def sulfur_func(so:str, annotations):
    return so in annotations


def camper_func(ko:str, annotations):
    return ko in annotations


def fegenie_func(ko:str, annotations):
    return ko in annotations


def pf_func(pf:str, annotations):
    return pf in annotations


class RuleParser():

    def __init__(self, rule_path:str, verbose:bool=False,
                 adjectives:set[str]=None):

        self.annotations = None
        self.G = nx.DiGraph()
        self.verbose = verbose
        self.data = pd.read_csv(rule_path, sep='\t')
        if not self.data['parent'].is_unique:
            dup_ids = self.data['parent'].duplicated(keep='first')
            dups = self.data['parent'][dup_ids].values
            raise SyntaxError(
                f"There are {len(dups)} duplicated parent name/names in"
                f" {rule_path}.\n"
                f"the duplicates are {dups}.\n"
                "you must correct these errors to continue.")
        self.data.set_index('parent', inplace=True)
        self.bipart_dict = {i:{
                j:self.data.loc[i,j] for j in self.data.columns
            } for i in self.data.index}
        selfidx = 0
        self.set_adjectives(adjectives) # automaticaly parses

    def set_adjectives(self, adjectives:set=None):
        adj_names = set(self.data['name'].dropna().values)
        if adjectives is None or len(adjectives) < 1:
            keep_adj = adj_names
        else:
            keep_adj = set(adjectives)
            if not keep_adj.issubset(adj_names):
                breakpoint()
                raise ValueError(
                    f"No such adjectives {keep_adj - adj_names}")
        self.root_nodes = set(
            self.data[
                self.data['name'].apply(lambda x: x in keep_adj)
            ].index.values)
        self.parse_rules()  # parse/reparse the rules

    def parse_rules(self):
        for i in self.root_nodes:
            self.parse(i)

    def parse(self, logic:str, parent:str=None):
        if self.verbose:
            print(f"Parsing: {logic}")
        if (line := self.bipart_dict.get(logic)) is not None:
            nodeid = logic
            self.G.add_node(nodeid,
                            display=nodeid,
                            type='name',
                            function=self.name_func,
                            genomes={})
            self.parse(line['child'], parent=nodeid)
            if parent:
                self.G.add_edge(parent, nodeid)
            return
        if (args := parse_functions(logic)) is not None:
            nodeid = logic
            self.G.add_node(nodeid,
                            display=args[0],
                            type=args[0],
                            function=None,
                            args=args[1],
                            genomes={})
            self.G.add_edge(parent, nodeid)
            if args[2] is not None:
                self.parse(args[2], parent=nodeid)
            return
        if re.match(r'^K[0-9,\.]+$', logic):
            nodeid = logic
            self.G.add_node(nodeid, display=nodeid, type='ko',
                            function=ko_func, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        if re.match(r'^D[0-9,\.]+$', logic):
            nodeid = logic
            self.G.add_node(nodeid, display=nodeid, type='camper',
                            function=camper_func, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        if re.match(r'^fe>[0-9A-z]+$', logic):
            nodeid = logic[3:]
            self.G.add_node(nodeid, display=nodeid, type='fegenie', function=fegenie_func, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        if re.match(r'^s>[0-9A-z]+$', logic):
            nodeid = logic[2:]
            self.G.add_node(nodeid, display=nodeid, type='sulfur', function=sulfur_func, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        if re.match(r'^PF\d+', logic):
            nodeid = logic
            self.G.add_node(nodeid, display=nodeid, type='PF',
                            function=pf_func, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        if re.match(r'^EC[0-9,\.]+[0-9,-]$', logic):
            nodeid = f"{logic[:2]}:{logic[2:]}"
            self.G.add_node(nodeid, display=nodeid, type='ec',
                            function=ec_func, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        if len(steps := parse_steps(logic))> 1:
            self.G.nodes[parent]['type'] = 'steps'
            for i, s  in enumerate(steps):
                nodeid = f"{parent}-step-{i}"
                self.G.add_node(nodeid, display=f"step-{i}",
                                type='step', function=None, genomes={})
                self.G.add_edge(parent, nodeid)
                self.parse(s, parent=nodeid)
            return
        if len(ors := parse_ors(logic))> 1:
            nodeid = f"{parent}-or"
            self.G.add_node(nodeid, display="or", type='or',
                            function=None, genomes={})
            self.G.add_edge(parent, nodeid)
            for i  in ors:
                self.parse(i, parent=nodeid)
            return
        if len(ands := parse_ands(logic))> 1:
            nodeid = f"{parent}-and"
            self.G.add_node(nodeid, display="and", type='and',
                            function=None, genomes={})
            self.G.add_edge(parent, nodeid)
            for i  in ands:
                self.parse(i, parent=nodeid)
            return
        if logic.startswith('[') and logic.endswith(']'):
            self.parse(logic[1:-1], parent=parent)
            return
        if logic == "False":
            nodeid = f"{parent}-False"
            self.G.add_node(nodeid, display="False", type='False',
                            function=None, genomes={})
            self.G.add_edge(parent, nodeid)
            return
        self.G.add_node(f"error = {logic}", display="error", type='error',
                            function=None, genomes={})
        self.G.add_edge(parent, f"error = {logic}")


    def add_to_dot(self, node):
        for i in self.G.successors(node):
            self.dot.edge(node, i)
            if self.G[node].get('type') != 'steps' or True:
                self.add_to_dot(i)

    def plot_rule(self, output_folder, adjectives:list=None,
                  show_steps=False):
        self.dot = graphviz.Digraph(strict=True)
        self.show_steps = show_steps
        if adjectives is None:
            adjectives = self.root_nodes
        for i in adjectives:
            self.add_to_dot(i)
        self.dot.render(os.path.join(output_folder, "All"), view=False)

    def add_to_dot_genome(self, node, genome, parent=None):
        match self.G.nodes[node].get('type'):
            case 'steps':
                count = sum(self.G.nodes[node]['genomes'][genome])
                total = len(self.G.nodes[node]['genomes'][genome])
                self.dot.node(
                    node,
                    f"{self.G.nodes[node]['display']} {count} of {total}",
                    color="grey")
                self.dot.edge(parent, node, color="grey")
                return
            case 'inGenomeCount':
                return
            case _:
                if self.G.nodes[node]['genomes'][genome]:
                    color = 'black'
                else:
                    color = "red"
        self.dot.node(node, self.G.nodes[node]['display'], color=color)
        if parent is not None:
            self.dot.edge(parent, node, color=color)
        for i in self.G.successors(node):
            # self.dot.edge(node, i)
            if self.G[node].get('type') != 'steps':
                self.add_to_dot_genome(i, genome, parent=node)

    def plot_adj_genome(self, output_folder, adj,  genome:str,
                        show_steps=False):
        self.dot = graphviz.Digraph(strict=True)
        self.show_steps = show_steps
        self.add_to_dot_genome(adj, genome)
        self.dot.render(os.path.join(output_folder, genome, adj), view=False)

    def plot_cause(self, output_folder, adjectives=None,
                                genomes=None,  show_steps=False):
        match (adjectives, genomes):
            case ((), ()):
                for adj in self.root_nodes:
                    for genome in self.annot.ids_by_fasta.index:
                        self.plot_adj_genome(output_folder, adj, genome,
                                             show_steps)
            case (_, ()):
                for adj in adjectives:
                    for genome in self.annot.ids_by_fasta.index:
                        self.plot_adj_genome(output_folder, adj, genome,
                                             show_steps)
            case ((), _):
                for adj in self.root_nodes:
                     for genome in genomes:
                         self.plot_adj_genome(output_folder, adj, genome,
                                              show_steps)
            case (_, _):
                for adj in adjectives:
                     for genome in genomes:
                         self.plot_adj_genome(output_folder, adj, genome,
                                              show_steps)
            case _:
                raise ValueError("There was an error in ploting the genomes.")

    def cycle_evaluate(self, node, genome_name:str, annotations:set):
        steps = [self.check_node(i, genome_name, annotations)
                 for i in self.G.successors(node)]
        self.G.nodes[node]['genomes'][genome_name] = steps
        return steps

    def atleastfunk(self, node, genome_name:str, annotations:set):
        count_val = int(self.G.nodes[node].get('args'))
        cycle_list = list(self.G.successors(node))
        cycle = cycle_list[0]
        if len(cycle_list) > 1 or self.G.nodes[cycle]['type'] != 'steps':
            raise ValueError("Count functions can only point to named cycles")
        steps = self.cycle_evaluate(cycle, genome_name, annotations)
        return sum(steps) >= count_val

    #TODO new class
    def percentfunk(self, node, genome_name:str, annotations:set):
        percent_val = float(self.G.nodes[node].get('args'))
        cycle_list = list(self.G.successors(node))
        cycle = cycle_list[0]
        if len(cycle_list) > 1 or self.G.nodes[cycle]['type'] != 'steps':
            raise ValueError("Percent functions can only point to"
                             " named cycles")
        steps = self.cycle_evaluate(cycle, genome_name, annotations)
        return ((sum(steps) / len(steps)) * 100) >= percent_val

    def name_func(self, node:str, genome_name:str, annotations:set):
        successor = list(self.G.successors(node))
        if len(successor) > 1:
            raise ValueError("A name can have only one child")
        return self.check_node(successor[0], genome_name, annotations)


    def step_func(self, node:str, genome_name:str, annotations:set):
        successor = list(self.G.successors(node))
        if len(successor) > 1:
            raise ValueError("A step can have only one child, this is a programing error")
        return self.check_node(successor[0], genome_name, annotations)


    # TODO make this a match
    def check_node(self, node:str, genome_name:str, annotations:set):
        #TODO method
        value = self.G.nodes[node]['genomes'].get(genome_name)
        if value is not None:
            return value
        value = self.evaluate_node(node, genome_name, annotations)
        self.G.nodes[node]['genomes'][genome_name] = value
        return value

    def check_genomes(self, annot:Annotations):
        # TODO make names and flags
        self.annot = annot
        output = annot.ids_by_fasta.apply(
            lambda x: {node:self.check_node(node, x.name, x.annotations)
                       for node in self.root_nodes},
            axis=1,
            result_type='expand')
        output.columns = self.data.loc[output.columns, 'name'].values
        return output

    def evaluate_node(self, node, genome_name, annotations):
        match self.G.nodes[node]['type']:
            case 'name':
                return self.name_func(node, genome_name, annotations)
            case 'step':
                return self.step_func(node, genome_name, annotations)
            case  'False':
                return False
            case  'True':
                return True
            case  'ec':
                return self.G.nodes[node]['function'](node, annotations)
            case  'ko':
                return self.G.nodes[node]['function'](node, annotations)
            case  'camper':
                return self.G.nodes[node]['function'](node, annotations)
            case  'sulfur':
                return self.G.nodes[node]['function'](node, annotations)
            case  'fegenie':
                return self.G.nodes[node]['function'](node, annotations)
            case  'pf':
                return self.G.nodes[node]['function'](node, annotations)
            case  'or':
                return np.any([self.check_node(i, genome_name, annotations)
                                for i in self.G.successors(node)])
            case  'and':
                return np.all([self.check_node(i, genome_name, annotations)
                                for i in self.G.successors(node)])
            case  'percent':
                return self.percentfunk(node, genome_name, annotations)
            case  'not':
                return not np.all([self.check_node(i, genome_name, annotations)
                                    for i in self.G.successors(node)])
            case  'columnvalue':
                # data = self.annot.data.copy()
                # data.set_index(['fasta', data.index], inplace=True)
                data = self.annot.data.loc[genome_name]
                arg_dict = self.G.nodes[node]['args']
                if arg_dict['comp'] == 'gt':
                    return int(arg_dict['val']) > sum(data[arg_dict['col']])
                else:
                    raise ValueError('NoT fully implimented')
            case  'columncontains':
                data = self.annot.data.loc[genome_name]
                arg_dict = self.G.nodes[node]['args']
                data.columns
                for i in data[arg_dict['col']].values:
                    if arg_dict['val'] in str(i):
                        return True
            case  'atleast':
                return self.atleastfunk(node, genome_name, annotations)
            # case  'inGenomeCount':
            # #TODO Fix
            #     successor = list(self.G.successors(node))
            #     if len(successor) > 1:
            #         raise ValueError("A inGenomeCount can have only one child,"
            #                          " this is a programing error")
            #     successor = successor[0]
            #     if self.annot.ids_by_row is None:
            #         self.annot.set_annotation_ids_by_row()
            #     count = sum(self.annot.ids_by_row.apply(
            #         lambda x: self.check_node(successor,
            #                                   x.name,
            #                                   x.annotations
            #                                   ),
            #         axis=1))
            #     return int(self.G.nodes[node]['args']) <= count
            case  'error':
                 raise TypeError(f"Something failed to parse! What is {node}")
            case _:
                raise ValueError(f"There was and error, in evaluation, no rule for {node}")

    def find_positve_leaves(self, adj):
        all_leaf_node = {n for n in nx.descendants(self.G, adj)
                         if self.G.nodes[n]['type'] in LEAF_NODES}
        nots = {i for n in nx.descendants(self.G, adj)
               if self.G.nodes[n]['type'] == 'not'
               for i in nx.descendants(self.G, n)
               if self.G.nodes[i]['type'] in LEAF_NODES}
        return all_leaf_node - nots
    # # TODO make this a match
    # def check_positive_genes(self, node:str, genome_name:str, annotations:set):
    #     #TODO method
    #     positive_genes = []
    #     match (self.G.nodes[node]['type'], self.G.nodes[node]['genomes'].get(genome_name)):
    #         case (_, False):
    #             return []
    #         case 'not', _:
    #         case _, True:
    #         case _, :
    #     if value is not None:
    #         return value
    #     value = self.evaluate_node(node, genome_name, annotations)
    #     self.G.nodes[node]['genomes'][genome_name] = value
    #     return value



def get_annot_data_for_positive_genes(annotations, fasta_names, positive_leaves):
    anno_data = (annotations.ids_by_row.loc[fasta_names]
                 .copy()
                 .apply(lambda x: set(x['annotations']), axis=1))
    # Check for count based positves
    additiv_cols = {
        j for i in positive_leaves.values()
        for j in i if j.startswith('columnvalue:gt:')}
    anno_counts = (
        annotations.data.loc[fasta_names]
        .copy()
        .apply(lambda x: {i for i in additiv_cols
                       if x[i.split(':')[-1]] > 0}, axis=1)
    )
    anno_data = pd.Series(
        [i | j for i, j in zip(anno_data.values, anno_counts.values)],
        index=anno_data.index)
    return anno_data


def get_positive_genes(rules, annotations, adjectives_dat):
    # transform the adjectives_dat
    names = rules.data['name'][~rules.data['name'].isna()].reset_index().set_index('name')['parent']
    adjectives_dat.columns = [names.loc[i] for i in adjectives_dat.columns]
    adj_data = (adjectives_dat.melt(ignore_index=False)
          .reset_index(drop=False)
          .rename(columns={'variable': 'adjective'})
          .set_index('value')
          .drop(index=False)
         )
    positive_leaves = {i: rules.find_positve_leaves(i)
                       for i in adj_data['adjective'].unique()}
    anno_data = get_annot_data_for_positive_genes(annotations,
                                      fasta_names = adj_data['fasta'].unique(),
                                      positive_leaves=positive_leaves)

    gene_adj = pd.concat([
        (pd.DataFrame(
            anno_data.loc[fa]
            .apply( lambda x: x & positive_leaves[aj]),
            columns=["positive_ids"]
        )
        .assign(fasta=fa)
        .assign(adjective=aj)
         )
        for fa, aj in zip(adj_data['fasta'].values, adj_data['adjective'].values) ])
    gene_adj = gene_adj[gene_adj['positive_ids'].apply(len) > 0]
    gene_adj['positive_ids'] = gene_adj['positive_ids'].apply(
        lambda x: ','.join(x))
    return gene_adj


""".
import os
import click
from rule_adjectives.rule_graph import RuleParser
from rule_adjectives.annotations import Annotations, get_ids_from_annotation
import pytest
import pandas as pd
import numpy

TEST_RULES_FILE = "tests/input_data/small_rules.tsv"
TEST_ANNOTATIONS_FILE = "tests/input_data/test_annotations.tsv"

from rule_adjectives.rule_graph import RuleParser
from rule_adjectives.annotations import Annotations, get_ids_from_annotation

rules = RuleParser(TEST_RULES_FILE, verbose=False)
annotations = Annotations(TEST_ANNOTATIONS_FILE)
adjectives_dat = rules.check_genomes(annotations)
get_positive_genes(rules, annotations, adjectives_dat)

import os
os.system('rule_adjectives /home/projects-wrighton-2/GROWdb/Yojoa_Hall/All_Med_High_bins/DRAM_per_bin/dRep_DRAM/merged_572_DRAM_annotations/annotations.tsv test.tsv')
"""
