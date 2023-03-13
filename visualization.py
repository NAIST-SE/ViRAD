import os
import copy
import csv
import sys
import re
from collections import Counter
from pathlib import Path
from graphviz import Digraph
from lxml import etree

# 使い方
USAGE_TEXT = """Usage: visualization.py cpp_file_dir output_dir [filter]
[filter] is a comma-separated list of node names excluded from output."""

# 対応する命令を探すための正規表現  
# advertise<型パラメータ>( 引数 ); のように関数呼び出しを捉える
# ROS1
ROS_PUBLISH_PATTERN = r"\Wadvertise(<[^\(]+>)?\((?P<param>[^;]+)\);"
ROS_SUBSCRIBE_PATTERN = r"\Wsubscribe(<[^\(]+>)?\((?P<param>[^;]+)\);"

# ROS2
ROS2_PUBLISH_PATTERN = r"\Wcreate_publisher(<[^\(]+>)?\((?P<param>[^;]+)\);"
ROS2_SUBSCRIBE_PATTERN = r"\Wcreate_subscription(<[^\(]+>)?\((?P<param>[^;]+)\);"

PUBLISH_PATTERNS = [ ROS_PUBLISH_PATTERN, ROS2_PUBLISH_PATTERN ]
SUBSCRIBE_PATTERNS = [ ROS_SUBSCRIBE_PATTERN, ROS2_SUBSCRIBE_PATTERN ]


# パラメータ内に登場する文字列リテラルを topic として抽出する
TOPIC_PATTERN = r"\"([^\"]+)\""

NON_LITERAL_TOPIC_PATTERN = r"([^\"]+)"

# pythonのlaunchファイルremapに関する情報を抽出
REMAP_FUNCTION_PATTERN = r"\WComposableNode\(.*?remappings\=\[.*?\]"
REMAP_NODE_FUNCTION_PATTERN = r"\WNode\(.*?remappings\=\[.*?\]"
 
NAME_PATTERN = r"name\=\"(?P<node>[^\"]+)\""
REMAPPINGS_PATTERN = r"remappings.+"

REMAP_PATTERN = r"\(\"(?P<original>[^\"]+)\",\s(?P<new>[^,]+)"

PYTHON_REMAP_LaunchConfiguration = r"LaunchConfiguration\(\"([^\"]+)\""
#PYTHON_REMAP_LaunchConfiguration = r"LaunchConfiguration"
PYTHON_REMAP_NOT_LaunchConfiguration = r"\"([^\"]+)\""

#PARAM_PATTERN = r"LaunchConfiguration\(\"(?P<param>[^\"]+)\"\)"
#REMAP_PATTERN = r"\(\"(?P<original>[^\"]+)\"\,\s\"(?P<new>[^\"]+)\"\)"

# xmlのlaunchファイルremapに関する情報を抽出
# defaultの抽出
XML_DEFAULT = r"\$\(var\s(?P<param>[^\"]+)\)"
REF_FILE = r"\$\([^)]+\)(?P<param>[^\s]+)"
REF_XML = r"([^.]+).launch.xml"

# ファイル検索 (glob) パターン
CPP_FILES = "**/*.cpp"
XML_FILES = "**/*.xml"
PYTHON_FILES = "**/*.py"

OUTPUT_FORMAT = 'svg'

def get_topic(lst: str):
    """Get a topic name from a code fragment. 

    This program assumes that a topic name is usually hard-coded in a literal.
    リテラルとして書かれているものがトピック名と仮定して識別します．

    :param lst: A code fragment including a topic name, 
        e.g. arguments of a subscribe function call.
    :returns: A pair of a topic name and a flag representing'literal' or 'non-literal'.
    """
    match = re.search(TOPIC_PATTERN, lst)
    non_match = re.search(NON_LITERAL_TOPIC_PATTERN, lst)
    if match:
        return match.group(1), 'literal'
    elif non_match:
        return non_match.group(1), 'non_literal'
    return None, None

def get_topics(text: str, patterns: list, file_name: str):
    """Find publish/subscriber patterns in source code.

    This function checks subscribe/publish function call patterns
    and extracts the topics used in the calls.

    :param text: Source code to be analyzed
    :param patterns: Regular expressions for finding topics.  
        Each pattern should have a group named 'param'.
        This function identifies identify a topic name from the part.
    :param file_name: A source file name. 
        This is included in the resultant list.
    :returns: A pair of identified topics and a list of source code locations.
        The identified topics is a set of strings.
        The source code locations is a list of tuples including four elements 
        (file name, start position, matched text, topic name).
    """
    topics = set()
    match_text = list()
    for pattern_text in patterns:
        pattern = re.compile(pattern_text, re.DOTALL)
        for match in pattern.finditer(text):
            topic, topic_type = get_topic(match.group('param'))
            if topic:
                topics.add(topic)
                match_text.append([file_name, match.start(), match.group(), topic])
            else:
                match_text.append([file_name, match.start(), match.group(), ""])
    return topics, match_text


class Node:
    def __init__(self, file_name):
        self.file_name = file_name
        self.name = os.path.splitext(os.path.basename(file_name))[0] # ファイル名からnode名を取得
        self.publishing_topics = set()
        self.subscribing_topics = set()
        self.locations = list()
        with open(file_name, encoding="utf-8") as file:
            text = file.read()
            self.publishing_topics, pub_locations = get_topics(text, PUBLISH_PATTERNS, file_name)
            self.subscribing_topics, sub_locations = get_topics(text, SUBSCRIBE_PATTERNS, file_name)
            self.locations = pub_locations + sub_locations


class RosGraph:
    def __init__(self, files):
        self.nodes = list()
        self.published_topics = Counter()
        self.subscribed_topics = Counter()
        for file_name in files:
            node = Node(file_name)
            self.nodes.append(node)
            self.published_topics.update(node.publishing_topics)
            self.subscribed_topics.update(node.subscribing_topics)
    
    """
    各ノードが publish している topic の一覧を[node,topic]の組のリストで返す
    """
    def get_pub_lst(self):
        pub_lst = list() # [node,topic]
        for node in self.nodes:
            for topic_name in node.publishing_topics: 
                pub_lst.append([node.name, topic_name])

        #non_connect_pub_out = r"C:\Users\mrtyu\Desktop\output7\pub.csv"
        #with open(non_connect_pub_out, 'w') as file:
        #    writer = csv.writer(file, lineterminator='\n')
        #    writer.writerow(['Topic', 'Node', 'FilePath'])
        #    writer.writerows(pub_lst)

        return pub_lst
    
    def get_sub_lst(self):
        sub_lst = list() # [topic,node]
        for node in self.nodes:
            for topic_name in node.subscribing_topics: # ファイル内のsubを[topic,node]で格納
                sub_lst.append([topic_name, node.name])
        return sub_lst
    
    def get_unsubscribed_topic_pulishers(self):
        unsubscribed_topics = self.published_topics.keys() - self.subscribed_topics.keys()
        unsubscribed_topic_pulishers = list()
        for node in self.nodes:
            for topic_name in (node.publishing_topics & unsubscribed_topics):
                unsubscribed_topic_pulishers.append([topic_name, node.name, node.file_name])
        return unsubscribed_topic_pulishers
    
    def get_unpublished_topic_subscribers(self):
        unpublished_topics = self.subscribed_topics.keys() - self.published_topics.keys()
        unpublished_topic_subscribers = list()
        for node in self.nodes:
            for topic_name in (node.subscribing_topics & unpublished_topics):
                unpublished_topic_subscribers.append([topic_name, node.name, node.file_name])
        return unpublished_topic_subscribers

class Remap:
    def __init__(self, xml_files, python_files, files):
        self.remap_rule_lst = list()

        for xml_file in xml_files:
            self.xml_reader(xml_file, files)
        for python_file in python_files:
            self.python_reader(python_file)
    
    def xml_reader(self, path, files):
        default_rule = list()
        remap_lst = list()
        ref_default_rules = list()
        ref_files = list()
        ref_flag = 0
        sec_ref_flag = 0

        with open(path, encoding="utf-8") as xml_file:
            tree = etree.parse(xml_file) 

        #defaultの取得
        args = tree.xpath('/launch/arg')
        if len(args):
            for arg in args:
                try:
                    default_rule.append([arg.attrib["name"], arg.attrib["default"]])
                except KeyError:
                    default_rule.append([arg.attrib["name"], arg.attrib["name"]])
    
        #passの取得
        tree_pass = '/launch/group'
        group = tree.xpath(tree_pass)

        if group:
            tree_pass = self.get_tree_pass(tree, tree_pass)
            node_path = tree_pass + '/node'
            remap_path = node_path + '/remap'
            set_remap_path = tree_pass + '/set_remap'
            
            new_tree_path = tree_pass[:-6]
            new_remap_path = self.remap_check(tree, new_tree_path)
            if new_remap_path:
                remap_path = new_remap_path
                node_path = remap_path[:-6]
                
        else:
            node_path = '/launch/node'
            remap_path = '/launch/node/remap'
            set_remap_path = '/launch/node/set_remap'
    
        #remapの取得
        remap_lst = self.make_remap_lst(tree, remap_path, default_rule)
        self.add_set_remap(tree, set_remap_path, default_rule)
        
        include_path = self.check_include(tree, '/launch')       
        if include_path:
            ref_default_rules, ref_flag, ref_files = self.include_remap(tree, include_path, files)
            sec_include_path = include_path[:-8] + '/group/include'
            sec_include = tree.xpath(sec_include_path)
            if sec_include:
                sec_ref_default_rules, sec_ref_flag, sec_ref_files = self.include_remap(tree, sec_include_path, files)

        if ref_flag == 1:
            self.add_include_remap(ref_files, ref_default_rules)

        if sec_ref_flag == 1:
            self.add_include_remap(sec_ref_files, sec_ref_default_rules)


        #node名の取得，remapリストの作成
        nodes = tree.xpath(node_path)
        base_number = 0
        remap_tag_count = 0

        if len(nodes):
            for node in nodes:
                node_name = node.attrib["pkg"]
                for child in node.iter():
                    if child.tag == 'remap':
                        remap_tag_count += 1
                for num in range(remap_tag_count - base_number):
                    self.remap_rule_lst.append([node_name, remap_lst[num + base_number][0], remap_lst[num + base_number][1], 'xml'])
            
                base_number = remap_tag_count + base_number

        return self.remap_rule_lst

    def get_tree_pass(self, tree, tree_pass):
        new_tree_pass = tree_pass + '/group'
        group = tree.xpath(new_tree_pass)
        if group:
            return self.get_tree_pass(tree, new_tree_pass)
        else:
            return tree_pass
    
    def make_remap_lst(self, tree, remap_path, default_rule):
        remap_lst = list()
        remaps = tree.xpath(remap_path)
        if remaps:
            for remap in remaps:
                original = remap.attrib["to"]
                match = re.search(XML_DEFAULT, remap.attrib["to"])

                if match:
                    original = match.group('param')
                    for lst in default_rule:
                        if original == lst[0]:
                            topic_name = lst[1]
                            break
                        else:
                            topic_name = original
                else:
                    topic_name = original
                remap_lst.append([remap.attrib["from"], topic_name])
        return remap_lst
    
    def add_set_remap(self, tree, set_remap_path, default_rule):
        set_remaps = tree.xpath(set_remap_path)
        if len(set_remaps):
            for set_remap in set_remaps:
                original = set_remap.attrib["to"]
                match = re.search(XML_DEFAULT, set_remap.attrib["to"])

                if match:
                    original = match.group('param')
                    for lst in default_rule:
                        if original == lst[0]:
                            topic_name = lst[1]
                            break
                        else:
                            topic_name = original
                else:
                    topic_name = original
                self.remap_rule_lst.append(['none',set_remap.attrib["from"], topic_name,'set'])
    
    def remap_check(self, tree, tree_path):
        node_path = tree_path + '/node'
        remap_path = node_path + '/remap'
        remap = tree.xpath(remap_path)
        if remap:
            return remap_path
        else:
            if tree_path == '/launch':
                return None                    
            else:
                group_path = tree_path[:-6]
                return self.remap_check(tree, group_path)
    
    def check_include(self, tree, path):
        include_path = path + '/include'
        include = tree.xpath(include_path)
        if include:
            return include_path
        
        group_path = path + '/group'
        group = tree.xpath(group_path)
        if group:
            return self.check_include(tree, group_path)
        else:
            return None
    
    def check_ref_path(self, tree, path):
        remap_path = path + '/node/remap'
        remap = tree.xpath(remap_path)
        if remap:
            return remap_path
        group_path = path + '/group'
        group =  tree.xpath(group_path)
        if group:
            return self.check_ref_path(tree, group_path)
        else:
            return None
    
    def include_remap(self, tree, include_path, files):

        ref_default_rules = list()
        ref_files = list()
        ref_flag = 0

        refs = tree.xpath(include_path)

        for ref in refs:
            ref_file = ref.attrib["file"]
            ref_match = re.search(REF_FILE, ref_file)
            match = re.search(REF_XML, ref_match.group('param'))

            if match:
                ref_flag = 1
                ref_file_name = '**' + match.group()

                ref_files = Path(files).glob(ref_file_name)
                include_arg_path = include_path + '/arg'
                include_args = tree.xpath(include_arg_path)
                if include_args:
                    for include_arg in include_args:
                        if include_arg.attrib["name"] != include_arg.attrib["value"]:
                            if include_arg.attrib["value"] != "" and include_arg.attrib["value"] != "true" and include_arg.attrib["value"] != "false": 
                                ref_default_rules.append([include_arg.attrib["name"], include_arg.attrib["value"]])
            return ref_default_rules, ref_flag, ref_files

    def add_include_remap(self, ref_files, ref_default_rules):
        for ref_file in ref_files:
            with open(ref_file, encoding="utf-8") as ref_xml_file:
                ref_tree = etree.parse(ref_xml_file)
            
            ref_remap_path = self.check_ref_path(ref_tree, '/launch')
            if ref_remap_path:
                ref_remaps = ref_tree.xpath(ref_remap_path)

                if len(ref_remaps):
                    for ref_remap in ref_remaps:
                        match = re.search(XML_DEFAULT, ref_remap.attrib["to"])
                        if match:
                            original = match.group('param')
                            for ref_default_rule in ref_default_rules:
                                if original == ref_default_rule[0]:
                                    self.remap_rule_lst.append(['none',ref_remap.attrib["from"], ref_default_rule[1],'arg'])
                                        
    def python_reader(self, path):
        with open(path, encoding="utf-8") as file:
                text = file.read()

        func_pattern = re.compile(REMAP_FUNCTION_PATTERN, re.DOTALL)
        func_node_pattern = re.compile(REMAP_NODE_FUNCTION_PATTERN, re.DOTALL)

        for func_text in func_pattern.finditer(text):
            self.make_remap_rules(func_text.group(),path) 

        for func_text in func_node_pattern.finditer(text):
            self.make_remap_rules(func_text.group(),path)        
    
    def make_remap_rules(self, text,path):
        name = re.search(NAME_PATTERN, text)

        if name:
            pattern = re.compile(REMAPPINGS_PATTERN, re.DOTALL)
            for remappings in pattern.finditer(text):
                if remappings:
                    self.get_remap_rules(remappings.group(), name.group('node'),path)
    
    def get_remap_rules(self, text, node,path):
        
        if re.search(REMAP_PATTERN, text):
            pattern = re.compile(REMAP_PATTERN, re.DOTALL)
            for match in pattern.finditer(text):
                lc_match = re.search(PYTHON_REMAP_LaunchConfiguration, match.group('new'))
                not_lc_match = re.search(PYTHON_REMAP_NOT_LaunchConfiguration, match.group('new'))

                if lc_match:
                    new_topic = '/' + lc_match.group(1)
                    self.remap_rule_lst.append([node, match.group('original'), new_topic, path])
                elif not_lc_match:
                    self.remap_rule_lst.append([node, match.group('original'), not_lc_match.group(1), path])

"""
[publisher-node, topic, subscriber-node の並び] のリストを返す
"""
def make_output_list(model, remaps): # テキスト化のためのリスト作成関数
    pub_list = list()
    sub_list = list()
    remap_list = list()
    output_list = list()

    pub_list = model.get_pub_lst()
    sub_list = model.get_sub_lst()
    remap_list = remaps.remap_rule_lst

    #pubのremap
    for pub in pub_list:
        for remap in remap_list[:]:
            #if pub[0] == remap[0] and pub[1] == remap[1]:
            if pub[1] == remap[1]:
                pub_list.append([pub[0], remap[2]])
                remap_list.remove(remap)

    #subのremap    
    for sub in sub_list:
        for remap in remap_list[:]:
            #if sub[1] == remap[0] and sub[0] == remap[1]:
            if sub[0] == remap[1]:
                sub_list.append([remap[2], sub[1]])
                remap_list.remove(remap)
    
    for pub in pub_list:
        output = list()

        for sub in sub_list:
            if pub[1] == sub[0]:
                output.append(sub[1])
        
        if len(output) > 0:
            connected = pub + output
            output_list.append(connected)

    return output_list

def del_element(lst, exclusion):
    del_lst = exclusion.split(',')
    copy_lst = copy.deepcopy(lst)

    for element in del_lst: 
        element_flag = 0
        for connection in copy_lst:
            pts_count = 0
            for pts in connection:

                if pts == element and pts_count != 1:
                    lst.remove(connection)
                    element_flag = 1
                    break
                elif pts == element:
                    connection.remove(pts)
                    element_flag = 1
                pts_count += 1
            
        if element_flag == 0:
            print("該当するnode，topicが存在しません．", element)
 
    return lst

def make_graph(lst, out_dir_name): # グラフ出力関数
    dg = Digraph(format=OUTPUT_FORMAT)
    dg.attr(rankdir='LR') # グラフを横向きに出力
    lst_count = 0
    dup_lst = [[]]
    dup_flag = 0
    topic_sub_count = 0

    for communication in lst:

        for element in communication:
            if lst_count == 0:
                pub = element
                dg.attr('node', shape='circle')
                dg.node(pub)
            elif lst_count == 1:
                topic = element
                dg.attr('node', shape='square')
                dg.node(topic)    
            else:
                sub = element
                dg.attr('node', shape='circle')
                dg.node(sub)
                topic_sub_count += 1
                if topic_sub_count == 1:
                    del(dup_lst[0])
            
            for topic_sub in dup_lst:
                if lst_count > 1:
                    if topic_sub[0] == topic and topic_sub[1] == sub:
                        dup_flag = 1 

            if lst_count == 1:
                dg.edge(pub, topic)
            elif dup_flag == 0 and lst_count > 1: # topic->subの矢印が重複しないようにする
                    dg.edge(topic, sub)
                    dup_lst.append([topic, sub])
            
            dup_flag = 0
            
            lst_count += 1

        lst_count = 0
    dg.render("connect_graph", out_dir_name, view=False) #ファイル出力

def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(USAGE_TEXT)
        return
    
    cpp_files = Path(sys.argv[1]).glob(CPP_FILES)
    out_dir_name = sys.argv[2]
    exclusion = sys.argv[3] if len(sys.argv)==4 else None
    out_dir = Path(out_dir_name)
    if out_dir.exists():
        if not out_dir.is_dir():
            print("Error: " + out_dir_name + " is not a directory.")
            return
    else:
        out_dir.mkdir(parents=True)
    
    model = RosGraph(cpp_files)

    #launchファイル名
    xml_files = Path(sys.argv[1]).glob(XML_FILES)
    python_files = Path(sys.argv[1]).glob(PYTHON_FILES)

    remaps = Remap(xml_files, python_files, sys.argv[1])

    remap_out = out_dir / "remap.csv"
    with open(remap_out, 'w') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerow(['Node', 'Original', 'New'])
        writer.writerows(remaps.remap_rule_lst)

    output_lst = make_output_list(model, remaps) # output用のリスト作成

    
    # 取得したpub，subの関係をcsvで出力する
    connect_out = out_dir / "connection.csv"
    with open(connect_out, 'w') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerows(output_lst)
    
    match_result = out_dir / "match.csv"
    with open(match_result, 'w') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerow(['Code', 'BytePos', 'Statement', 'Topic'])
        for node in model.nodes:
            writer.writerows(node.locations)
    
    non_connect_pub_out = out_dir / "non_connect_pub.csv"
    with open(non_connect_pub_out, 'w') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerow(['Topic', 'Node', 'FilePath'])
        writer.writerows(model.get_unsubscribed_topic_pulishers())
    
    non_connect_sub_out = out_dir / "non_connect_sub.csv"
    with open(non_connect_sub_out, 'w') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerow(['Topic', 'Node', 'FilePath'])
        writer.writerows(model.get_unpublished_topic_subscribers())


    if exclusion:
        output_lst = del_element(output_lst, exclusion)
    make_graph(output_lst, out_dir_name)

if __name__ == "__main__":
    main()