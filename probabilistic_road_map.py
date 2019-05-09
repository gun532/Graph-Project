import random
import math
import time
import multiprocessing
import numpy as np
import building_models
import matplotlib.pyplot as plt
from KDTree import KDTree
from Graph import Graph
from timer_decorator import timer
from timer_decorator import calculate_average_time
from mpl_toolkits.mplot3d import Axes3D
from Node import Node
from functools import partial


# parameter
DEFAULT = 1.0
N_KNN = 10  # number of edge from one sampled point
TOTAL_TIME = 0
MAX_EDGE_LEN = 30.0 * DEFAULT
N_SAMPLE = 500 * DEFAULT
ALGORITHM = "a_star"
X = list()
Y = list()
Z = list()

show_animation = True


def _get_algorithm_function(algorithm_name):
    if algorithm_name == 'dijkstra':
        return dijkstra_planning
    elif algorithm_name == 'a_star':
        return a_star_planning
    else:
        raise ValueError("This algorithm can't be found!")


def find_min_time(time_list):
    return time_list.index(min(time_list)), min(time_list)


@timer
def prm_planning(obstacle_x, obstacle_y, robot_radius, algorithm_name, data_graph):
    result_tuple_list = list()
    total_time_list = list()
    goal_list_tuple = list()
    obkdtree = KDTree(np.vstack((obstacle_x, obstacle_y)).T)
    algorithms = _get_algorithm_function(algorithm_name)

    for index in range(len(data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_x'])):
        goal_tuple = (data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_x'][index] * DEFAULT,
                      data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_y'][index] * DEFAULT,
                      data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_z'][index] * DEFAULT)

        sample_x, sample_y = sample_points(data_graph.starting_point, goal_tuple, robot_radius, obstacle_x, obstacle_y, obkdtree)

        # if show_animation:
        #     plt.plot(sample_x, sample_y, ".b")
        road_map = generate_roadmap(sample_x, sample_y, robot_radius, obkdtree)

        result_x, result_y, total_time, return_code = algorithms(data_graph.starting_point, goal_tuple, sample_x, sample_y, road_map)
        result_tuple_list.append((result_x, result_y, return_code))
        total_time_list.append(total_time)
        goal_list_tuple.append(goal_tuple)
        # print(f"result x:{len(result_x)}, y:{len(result_y)}")

    min_index, min_time = find_min_time(total_time_list)
    data_graph.goal_point = goal_list_tuple[min_index]
    return result_tuple_list[min_index][0], result_tuple_list[min_index][1],\
        min_index, min_time, result_tuple_list[min_index][2]


def a_star_planning(start_tuple, goal_tuple, sample_x, sample_y, road_map):
    start_node = Node(start_tuple[0], start_tuple[1], 0.0, -1)
    goal_node = Node(goal_tuple[0], goal_tuple[1], 0.0, -1)
    open_set, closed_set = dict(), dict()
    open_set[len(road_map) - 2] = start_node
    total_time = 0
    break_flag = 0
    while True:
        if not open_set:
            print("Cannot find path")
            break_flag = 1
            break

        current_id = min(open_set, key=lambda o: open_set[o].cost + calc_heuristic(goal_node, open_set[o]))
        current = open_set[current_id]

        if current_id == (len(road_map) - 1):
            print("Find goal")
            goal_node.pind = current.pind
            goal_node.cost = current.cost
            break

        # Remove the item from the open set
        open_set.pop(current_id)
        # Add it to the closed set
        closed_set[current_id] = current

        # expand search grid based on motion model
        for i in range(len(road_map[current_id])):
            neighbour_id = road_map[current_id][i]
            dx = sample_x[neighbour_id] - current.x
            dy = sample_y[neighbour_id] - current.y
            # todo dont add time to node, switch to distance
            distance = math.sqrt(dx ** 2 + dy ** 2)
            node = Node(sample_x[neighbour_id], sample_y[neighbour_id], distance, current_id)

            if neighbour_id in closed_set:
                continue

            if neighbour_id not in open_set:
                open_set[neighbour_id] = node  # Discover a new node
            else:
                if open_set[neighbour_id].cost >= node.cost:
                    # This path is the best until now. record it!
                    open_set[neighbour_id] = node

    result_x, result_y, total = [goal_node.x], [goal_node.y], [goal_node.cost]
    pind = goal_node.pind
    while pind != -1:
        n = closed_set[pind]
        result_x.append(n.x)
        result_y.append(n.y)
        total.append(n.cost)
        pind = n.pind

    total_distance = 0
    for value in total:
        total_distance += value
    print(f"total distance (meters): {total_distance}")
    print(f"Total time in minutes: {weight_on_sub_path(total_distance)}")
    return result_x, result_y, total_distance, break_flag


def dijkstra_planning(start_tuple, goal_tuple, sample_x, sample_y, road_map):
    start_node = Node(start_tuple[0], start_tuple[1], 0.0, -1)
    goal_node = Node(goal_tuple[0], goal_tuple[1], 0.0, -1)

    open_set, closed_set = dict(), dict()
    open_set[len(road_map) - 2] = start_node

    flag = 0
    while True:
        if not open_set:
            print("Cannot find path")
            flag = 1
            break

        current_id = min(open_set, key=lambda o: open_set[o].cost)
        current = open_set[current_id]

        if current_id == (len(road_map) - 1):
            print("Goal is found!")
            goal_node.pind = current.pind
            goal_node.cost = current.cost
            break

        # Remove the item from the open set
        open_set.pop(current_id)
        # Add it to the closed set
        closed_set[current_id] = current

        # expand search grid based on motion model
        for i in range(len(road_map[current_id])):
            neighbour_id = road_map[current_id][i]
            distance_x = sample_x[neighbour_id] - current.x
            distance_y = sample_y[neighbour_id] - current.y
            # total_time = weight_on_sub_path(math.sqrt(distance_x**2 + distance_y**2))
            distance = math.sqrt(distance_x ** 2 + distance_y ** 2)

            node = Node(sample_x[neighbour_id], sample_y[neighbour_id], distance, current_id)

            if neighbour_id in closed_set:
                continue
            # Otherwise if it is already in the open set
            if neighbour_id in open_set:
                if open_set[neighbour_id].cost > node.cost:
                    open_set[neighbour_id].cost = node.cost
                    open_set[neighbour_id].pind = current_id
            else:
                open_set[neighbour_id] = node

    # generate final course
    result_x, result_y, total = [goal_node.x], [goal_node.y], [goal_node.cost]
    pind = goal_node.pind

    while pind != -1:
        n = closed_set[pind]
        result_x.append(n.x)
        result_y.append(n.y)
        total.append(n.cost)
        pind = n.pind

    amount_of_total = 0
    for value in total:
        amount_of_total += value
    print(f"total distance (meters): {amount_of_total}")
    print(f"total time in minutes: {weight_on_sub_path(amount_of_total)}")

    return result_x, result_y, amount_of_total, flag


#   400 meters per minute = 24 KMH
def weight_on_sub_path(distance, average_speed=250.0):
    return distance / average_speed


def calc_heuristic(n1, n2):
    factored_weight = 1.0
    distance = factored_weight * math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2)
    return distance


def is_collision(start_x, start_y, goal_x, goal_y, robot_radius, okdtree):
    x = start_x
    y = start_y
    dx = goal_x - start_x
    dy = goal_y - start_y
    yaw = math.atan2(goal_y - start_y, goal_x - start_x)
    d = math.sqrt(dx**2 + dy**2)

    if d >= MAX_EDGE_LEN:
        return True

    D = robot_radius
    nstep = round(d / D)

    for i in range(nstep):
        idxs, dist = okdtree.search(np.array([x, y]).reshape(2, 1))
        if dist[0] <= robot_radius:
            return True  # collision
        x += D * math.cos(yaw)
        y += D * math.sin(yaw)

    # goal point check
    idxs, dist = okdtree.search(np.array([goal_x, goal_y]).reshape(2, 1))
    if dist[0] <= robot_radius:
        return True  # collision

    return False  # OK


def generate_roadmap(sample_x, sample_y, robot_radius, obkdtree):
    """
    Road map generation
    sample_x: [m] x positions of sampled points
    sample_y: [m] y positions of sampled points
    robot_radius: Robot Radius[m]
    obkdtree: KDTree object of obstacles
    """

    road_map = []
    nsample = len(sample_x)
    skdtree = KDTree(np.vstack((sample_x, sample_y)).T)

    for (i, ix, iy) in zip(range(nsample), sample_x, sample_y):

        index, dists = skdtree.search(
            np.array([ix, iy]).reshape(2, 1), k=nsample)
        inds = index[0]
        edge_id = []

        for ii in range(1, len(inds)):
            nx = sample_x[inds[ii]]
            ny = sample_y[inds[ii]]

            if not is_collision(ix, iy, nx, ny, robot_radius, obkdtree):
                edge_id.append(inds[ii])

            if len(edge_id) >= N_KNN:
                break

        road_map.append(edge_id)

    return road_map


def plot_road_map(road_map, sample_x, sample_y):  # pragma: no cover

    for i, _ in enumerate(road_map):
        for ii in range(len(road_map[i])):
            ind = road_map[i][ii]

            plt.plot([sample_x[i], sample_x[ind]],
                     [sample_y[i], sample_y[ind]], "-k")


def sample_points(start_tuple, goal_tuple, robot_radius, obstacle_x, obstacle_y, obkdtree):
    max_x = max(obstacle_x)
    max_y = max(obstacle_y)
    min_x = min(obstacle_x)
    min_y = min(obstacle_y)
    sample_x, sample_y = list(), list()

    while len(sample_x) <= N_SAMPLE:
        random_x = (random.random() - min_x) * (max_x - min_x)
        random_y = (random.random() - min_y) * (max_y - min_y)
        index, dist = obkdtree.search(np.array([random_x, random_y]).reshape(2, 1))

        if dist[0] >= robot_radius:
            sample_x.append(random_x)
            sample_y.append(random_y)

    sample_x.append(start_tuple[0])
    sample_y.append(start_tuple[1])
    sample_x.append(goal_tuple[0])
    sample_y.append(goal_tuple[1])
    return sample_x, sample_y


def _get_building_model(model_name, floor_number=''):
    if model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_1':
        return building_models.outline_obstacles_demo_building_1
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_2':
        return building_models.outline_obstacles_demo_building_2
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_3':
        return building_models.outline_obstacles_demo_building_3
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_4':
        return building_models.outline_obstacles_demo_building_4
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_5':
        return building_models.outline_obstacles_demo_building_5
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_6':
        return building_models.outline_obstacles_demo_building_6
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_7':
        return building_models.outline_obstacles_demo_building_7
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_8':
        return building_models.outline_obstacles_demo_building_8
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_9':
        return building_models.outline_obstacles_demo_building_9
    elif model_name == 'OUTLINE_OBSTACLES_DEMO_BUILDING_10':
        return building_models.outline_obstacles_demo_building_10
    elif model_name == 'BUILDING_8_HIT':
        return _get_floor_function_building_8_hit(floor_number)
    else:
        raise ValueError('This building does not exist here...')


def _get_floor_function_building_8_hit(i_floor_number):
    if i_floor_number == 1:
        return building_models.outline_obstacles_floor_one
    elif i_floor_number == 2:
        return building_models.outline_obstacles_floor_two_and_three
    elif i_floor_number == 3:
        return building_models.outline_obstacles_floor_two_and_three
    elif i_floor_number == 4:
        return building_models.outline_obstacles_floor_four
    else:
        raise ValueError(i_floor_number)


def create_3d_graph(x, y, z):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.plot(x, y, z)
    ax.scatter(x, y, z, zdir='z', lw=2, c='r', marker='*')
    plt.show()


def main(data_graph, algorithm_name):
    # print(__file__ + " start!!")
    robot_size = 1.0 * DEFAULT

    obstacle_x, obstacle_y = list(), list()

    current_floor = _get_building_model(data_graph.model_name, data_graph.current_floor)
    obstacle_x, obstacle_y = current_floor(obstacle_x, obstacle_y)

    result_x, result_y, min_index, current_min_time, return_code = prm_planning(obstacle_x, obstacle_y, robot_size,
                                                                                algorithm_name, data_graph)

    data_graph.total_min_time += current_min_time
    # if show_animation and return_code == 0:
    if show_animation:
        print(f"return code is: {return_code}")
        plt.plot(obstacle_x, obstacle_y, ".k")
        plt.plot(data_graph.starting_point[0],
                 data_graph.starting_point[1], "^r")
        plt.plot(graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_x'][min_index] * DEFAULT,
                 graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_y'][min_index] * DEFAULT, "^g")
        plt.grid(True)
        plt.axis("equal")

    assert result_x, 'Cannot find path'

    #   todo change to floor's actual height
    for i in range(len(result_x)):
        Z.append(float((60 * DEFAULT) * (data_graph.current_floor-1)))

    X.extend(result_x)
    Y.extend(result_y)
    if show_animation:
        plt.plot(result_x, result_y, "-r")
        plt.show()

    if return_code != 0:
        return False

    data_graph.goal_point = data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_x'][min_index] * DEFAULT, \
        data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_y'][min_index] * DEFAULT,\
        data_graph.coordinate['Building'][data_graph.model_name]['Floors'][str(data_graph.current_floor)]['goal_z'][min_index] * DEFAULT

    return True


if __name__ == '__main__':
    average_of_run = 0
    graph = Graph('floors.yaml', 'BUILDING_8_HIT', 4)
    amount = 10
    amount_of_plots = 0
    for i in range(amount):
        exit_flag = True
        tries = 0
        # print(f"current index is: {i} out of {amount}")
        # graph.randomize_graph_selection()
        # print(f"Current graph is {graph.model_name}")
        # graph.randomize_floor_selection()
        # print(f"Current floor is {graph.current_floor}")
        graph.prioritize_starting_points()
        # graph.randomize_start_points()
        current_floor = graph.current_floor
        for c_index in range(len(graph.starting_nodes)):
            amount_of_plots += 1
            graph.current_floor = current_floor # todo put this somewhere else
            graph.starting_point = graph.starting_nodes[c_index].x, graph.starting_nodes[c_index].y, \
                                   graph.starting_nodes[c_index].z
            print(f"starting point number {graph.starting_point}")
            # start_time = time.time()
            while exit_flag:
                if tries > 10:
                    break
                exit_flag = main(graph, ALGORITHM)

                if not exit_flag:
                    print(f'Returned from floor {graph.current_floor} unsuccessfully')
                    tries += 1
                    amount_of_plots += 1
                    exit_flag = True
                    continue
                else:
                    print(f'Returned successfully from floor {graph.current_floor}')
                    tries = 1
                    if c_index == len(graph.starting_nodes) - 1 or graph.current_floor > 1:
                        graph.current_floor -= 1
                    else:
                        break

                if graph.current_floor < 1:
                    break
                else:
                    graph.starting_point = graph.goal_point[0], graph.goal_point[1] - (3.5 * DEFAULT), \
                                           graph.coordinate['Building'][graph.model_name]['Floors'][str(graph.current_floor)]['start_z'][0] * DEFAULT
                    graph.total_min_time += graph.calc_height_distance()

            # average_of_run += (end_time - start_time)
            print(f"Graph total time is: {graph.total_min_time}")
            create_3d_graph(X, Y, Z)
            X, Y, Z = graph.clear_x_y_z_lists(X, Y, Z)
            graph.total_min_time = 0
        graph.starting_nodes.clear()
        # graph.delete_current_model()
    average_of_run /= amount
    calculate_average_time(amount_of_plots)
    print(f"Finished Experiment on {ALGORITHM} algorithm. Average is: {average_of_run}")
    exit(0)
