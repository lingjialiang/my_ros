#!/usr/bin/env python
# -*- coding:utf-8 -*-

import rospy
import actionlib
from smach import State,StateMachine
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from std_msgs.msg import String
import time

#目標地点リスト　名前, 座標, 向き
room_waypoints = {
    "Room01":[["door_key_1", (-1.4, -2.7), (0.0, 0.0, 0.149230403361, 0.988802450802)],
              ["room", ( 2.9,  0.0), (0.0, 0.0, 0.974797896522, 0.223089804646)],
              ["door_key_2", (-1.4, -2.7), (0.0, 0.0, 0.149230403361, -0.988802450802)]],
    "Room02":[["door_free_1", (-1.4, -2.7), (0.0, 0.0, 0.149230403361, 0.988802450802)],
              ["room", ( 2.9,  0.0), (0.0, 0.0, 0.974797896522, 0.223089804646)],
              ["door_free_2", (-1.4, -2.7), (0.0, 0.0, 0.149230403361, -0.988802450802)]]
}
initialpoint = [(-1.09, 2.48), (0.0, 0.0, -0.739811508606, 0.672814188119)]

#waypoints = [
#    ["Room01", (-1.4, -2.7), (0.0, 0.0, 0.149230403361, 0.988802450802)],
#    ["Room02", (2.9, 0.0), (0.0, 0.0, 0.974797896522, 0.223089804646)],
#    ["Room03", (-1.09, 2.48), (0.0, 0.0, -0.739811508606, 0.672814188119)]
#]
#waypointsから目標地点名のみ抽出
room_names = []
for w in room_waypoints:
    room_names.append(w)

class Waypoint(State):
    def __init__(self, position, orientation, status):
        State.__init__(self, outcomes=['success'])

        self.status = status
        #move_baseをクライアントとして定義
        self.client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        self.client.wait_for_server()

        #目標地点を定義
        self.goal = MoveBaseGoal()
        self.goal.target_pose.header.frame_id = 'map'
        self.goal.target_pose.pose.position.x = position[0]
        self.goal.target_pose.pose.position.y = position[1]
        self.goal.target_pose.pose.position.z = 0.0
        self.goal.target_pose.pose.orientation.x = orientation[0]
        self.goal.target_pose.pose.orientation.y = orientation[1]
        self.goal.target_pose.pose.orientation.z = orientation[2]
        self.goal.target_pose.pose.orientation.w = orientation[3]

    def execute(self, userdata):
        #目標地点を送信し結果待ち
        pub=rospy.Publisher('turtlebot_status', String)
        self.client.send_goal(self.goal)
        self.client.wait_for_result()
        pub.publish(self.status)
        return 'success'

#次の目標地点名の受信待ち
class Reception(State):
    def __init__(self):
        State.__init__(self,outcomes=room_names)
        self.callback_flag= 0
        self.next_goal = ''
        self.r = rospy.Rate(1)
    def execute(self,userdata):
        sub = rospy.Subscriber('next_goal',String, self.callback)
        while(self.callback_flag == 0):
            self.r.sleep()
        self.callback_flag =0
        return self.next_goal
        
    def callback(self,msg):
        if (msg.data in room_names and self.next_goal != msg.data):
            self.next_goal = msg.data
            self.callback_flag = 1

#start_flag待ち
class WaitStartFlag(State):
    def __init__(self):
        State.__init__(self,outcomes=['success'])
        self.callback_flag= 0
        self.r = rospy.Rate(1)
    def execute(self,userdata):
        sub = rospy.Subscriber('start_flag',String, self.callback)
        while(self.callback_flag == 0):
            self.r.sleep()
        self.callback_flag =0
        return 'success'
    def callback(self,msg):
        self.callback_flag = 1

#部屋まで移動
class MoveToRoom(State):
    def __init__(self):
        State.__init__(self,outcomes=['success'])
    def execute(self,userdata):
        return 'success'

if __name__ == '__main__':
    rospy.init_node('operator')
    operator = StateMachine(['success','reception','move_to_reception'] + room_names)
    reception_transitions={}
    for r in room_names:
        reception_transitions[r] = r
    with operator:
        #受けつけ、受付まで移動状態を追加
        StateMachine.add('move_to_reception',Waypoint(initialpoint[0], initialpoint[1], 'reception'),
                         transitions={'success':'reception'})
        StateMachine.add('reception',Reception(),
                         transitions=reception_transitions)

        for r in room_names:
            waypoints = room_waypoints[r]
            next_move_state_names = []# [Room01_door_key_1, Room01_room]
            next_wait_state_names = []# [Room01_door_key_1_wait, Room01_room_wait]
            for i,w in enumerate(waypoints):
                    next_move_state_names.append(r+'_'+w[0])
                    next_wait_state_names.append(r+'_'+w[0]+'_wait')
            operator.register_outcomes(next_move_state_names+next_wait_state_names)

            StateMachine.add(r,MoveToRoom(),transitions={'success':next_move_state_names[0]})
            for i,w in enumerate(waypoints):
                if i < len(waypoints) - 1:
                    StateMachine.add(next_move_state_names[i],
                                     Waypoint(w[1], w[2], next_move_state_names[i]),
                                     transitions={'success':next_wait_state_names[i]})
                    StateMachine.add(next_wait_state_names[i],
                                     WaitStartFlag(),
                                     transitions={'success':next_move_state_names[i+1]})
                else:
                    StateMachine.add(next_move_state_names[i],
                                     Waypoint(w[1], w[2], next_move_state_names[i]),
                                     transitions={'success':next_wait_state_names[i]})
                    StateMachine.add(next_wait_state_names[i],
                                     WaitStartFlag(),
                                     transitions={'success':'move_to_reception'})
    operator.execute()
    