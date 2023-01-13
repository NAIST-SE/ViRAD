import sys
import copy
import csv
from graphviz import Digraph

dg = Digraph(format='png')
dg.attr(rankdir='LR')
call = 0
dp_topic_sub = [[]]

def draw_design(judge, lst):
    
    global call
    lst_count = 0
    dp_flag = 0

    for element in lst:
        if lst_count == 0:
            pub = element
            if judge == 'same':
                dg.attr('node', shape='circle')
                dg.node(pub, color = 'black')
            elif judge == 'new':
                dg.attr('node', shape='circle')
                dg.node(pub, penwidth="3", color = '#d9534f') 

        elif lst_count == 1:
            topic = element
            if judge == 'same':
                dg.attr('node', shape='square')
                dg.node(topic, color = 'black')   
            elif judge == 'new':
                dg.attr('node', shape='square')
                dg.node(topic, penwidth="3", color = '#d9534f') 

        elif lst_count > 1:
            sub = element
            if sub != '':
                if judge == 'same':
                    dg.attr('node', shape='circle')
                    dg.node(sub, color = 'black')
                elif judge == 'new':
                    dg.attr('node', shape='circle')
                    dg.node(sub, penwidth="3", color = '#d9534f')

            if call > 0:
                for topic_sub in dp_topic_sub:
                    if topic_sub[0] == topic and topic_sub[1] == sub:
                        dp_flag = 1
            dp_topic_sub.append([topic,sub])
            call += 1

        if lst_count == 1:
            if judge == 'same':
                dg.edge(pub, topic, color = 'black')
            elif judge == 'new':
                dg.edge(pub, topic, penwidth="3", color = '#d9534f')
        elif lst_count > 1 and dp_flag == 0 and sub != '': # topic->subの矢印が重複しないようにする
            if judge == 'same':
                dg.edge(topic, sub, color = 'black')
            elif judge == 'new':
                dg.edge(topic, sub, penwidth="3", color = '#d9534f')

        lst_count += 1
        dp_flag = 0
        if call == 1 and lst_count > 1:
            del(dp_topic_sub[0])

def diff():

    try:
        new_file_path = sys.argv[1]
        new_file = open(new_file_path)
    except OSError as e:
        print(e)
        sys.exit( )
    try:
        past_file_path = sys.argv[2]
        past_file = open(past_file_path)
    except OSError as e:
        print(e)
        sys.exit( )

    new_reader = csv.reader(new_file)
    past_reader = csv.reader(past_file)
    new_data = [ list(n) for n in new_reader ]
    past_data = [ list(p) for p in past_reader ]
    copy_new_data = copy.deepcopy(new_data)
    copy_past_data = copy.deepcopy(past_data)

    for new_connection in copy_new_data:
        for past_connection in copy_past_data:
            if new_connection == past_connection:
                draw_design('same', new_connection)
                past_data.remove(past_connection)
                new_data.remove(new_connection)
    
    if len(new_data) != 0:
        for new_connection in new_data:
            draw_design('new', new_connection)

    new_file.close
    past_file.close
    dg.render("diff_graph", sys.argv[3] ,view=True) #ファイル出力

def main():

    if len(sys.argv) != 4:
        print('ファイル数が異なります')
        sys.exit() 
    diff()

if __name__ == "__main__":
    main()