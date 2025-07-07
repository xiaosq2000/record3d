cmake_minimum_required(VERSION 3.0.2)
project(record3d_ros)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  rospy
  sensor_msgs
  tf2_ros
)

catkin_package()

catkin_install_python(
  PROGRAMS scripts/record3d_ros_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
