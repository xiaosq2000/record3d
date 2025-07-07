#!/usr/bin/env python

import threading

import cv2
import rospy
import tf2_ros
from geometry_msgs.msg import TransformStamped
from record3d import Record3DStream
from sensor_msgs.msg import CameraInfo, Image


class Record3DRosPublisher:
    def __init__(self):
        rospy.init_node("record3d_streamer")

        self.DEVICE_TYPE__TRUEDEPTH = 0
        self.DEVICE_TYPE__LIDAR = 1

        # Get params from the parameter server
        self.device_index = rospy.get_param("~device_index", 0)
        self.map_frame_id = rospy.get_param("~map_frame_id", "map")
        self.camera_frame_id = rospy.get_param("~camera_frame_id", "camera_link")

        rgb_topic = rospy.get_param("~rgb_topic", "/camera/color/image_raw")
        depth_topic = rospy.get_param("~depth_topic", "/camera/depth/image_raw")
        confidence_topic = rospy.get_param("~confidence_topic", "/camera/confidence/image_raw")
        cam_info_topic = rospy.get_param("~camera_info_topic", "/camera/color/camera_info")

        # Setup publishers
        self.rgb_pub = rospy.Publisher(rgb_topic, Image, queue_size=10)
        self.depth_pub = rospy.Publisher(depth_topic, Image, queue_size=10)
        self.confidence_pub = rospy.Publisher(confidence_topic, Image, queue_size=10)
        self.cam_info_pub = rospy.Publisher(cam_info_topic, CameraInfo, queue_size=10)

        self.tf_broadcaster = tf2_ros.TransformBroadcaster()

        self.session = None
        self.event = threading.Event()
        self.connect_to_device()

    def on_new_frame(self):
        """Called from a non-main thread when a new frame is available."""
        rospy.loginfo("New frame event triggered.")
        self.event.set()

    def on_stream_stopped(self):
        rospy.loginfo("Stream stopped")

    def connect_to_device(self):
        rospy.loginfo("Searching for devices...")
        devs = Record3DStream.get_connected_devices()
        rospy.loginfo(f"{len(devs)} device(s) found.")
        for dev in devs:
            rospy.loginfo(f"\tID: {dev.product_id}\n\tUDID: {dev.udid}\n")

        if len(devs) <= self.device_index:
            rospy.logerr(f"Cannot connect to device #{self.device_index}. Try a different index.")
            raise RuntimeError("Cannot connect to device")

        dev = devs[self.device_index]
        self.session = Record3DStream()
        self.session.on_new_frame = self.on_new_frame
        self.session.on_stream_stopped = self.on_stream_stopped
        self.session.connect(dev)
        rospy.loginfo("Successfully connected to device.")

    def publish_images(self, ts, rgb, depth, confidence):
        # RGB image
        rgb_msg = Image()
        rgb_msg.header.stamp = ts
        rgb_msg.header.frame_id = self.camera_frame_id
        rgb_msg.height = rgb.shape[0]
        rgb_msg.width = rgb.shape[1]
        rgb_msg.encoding = "rgb8"
        rgb_msg.is_bigendian = 0
        rgb_msg.step = rgb.shape[1] * 3
        rgb_msg.data = rgb.tobytes()
        self.rgb_pub.publish(rgb_msg)

        # Depth image
        depth_msg = Image()
        depth_msg.header.stamp = ts
        depth_msg.header.frame_id = self.camera_frame_id
        depth_msg.height = depth.shape[0]
        depth_msg.width = depth.shape[1]
        depth_msg.encoding = "32FC1"
        depth_msg.is_bigendian = 0
        depth_msg.step = depth.shape[1] * 4
        depth_msg.data = depth.astype("float32").tobytes()
        self.depth_pub.publish(depth_msg)

        if confidence.size > 0:
            # The confidence map uses values 0, 1, 2. We scale them to be visible in an image viewer.
            confidence_scaled = (confidence * 100).astype("uint8")
            confidence_msg = Image()
            confidence_msg.header.stamp = ts
            confidence_msg.header.frame_id = self.camera_frame_id
            confidence_msg.height = confidence_scaled.shape[0]
            confidence_msg.width = confidence_scaled.shape[1]
            confidence_msg.encoding = "mono8"
            confidence_msg.is_bigendian = 0
            confidence_msg.step = confidence_scaled.shape[1]
            confidence_msg.data = confidence_scaled.tobytes()
            self.confidence_pub.publish(confidence_msg)

    def publish_camera_info(self, ts, intrinsic_coeffs, width, height):
        cam_info_msg = CameraInfo()
        cam_info_msg.header.stamp = ts
        cam_info_msg.header.frame_id = self.camera_frame_id
        cam_info_msg.width = width
        cam_info_msg.height = height

        cam_info_msg.K = [
            intrinsic_coeffs.fx,
            0,
            intrinsic_coeffs.tx,
            0,
            intrinsic_coeffs.fy,
            intrinsic_coeffs.ty,
            0,
            0,
            1,
        ]

        cam_info_msg.P = [
            intrinsic_coeffs.fx,
            0,
            intrinsic_coeffs.tx,
            0,
            0,
            intrinsic_coeffs.fy,
            intrinsic_coeffs.ty,
            0,
            0,
            0,
            1,
            0,
        ]

        cam_info_msg.D = [0.0, 0.0, 0.0, 0.0, 0.0]
        cam_info_msg.distortion_model = "plumb_bob"

        self.cam_info_pub.publish(cam_info_msg)

    def publish_transform(self, ts, pose):
        t = TransformStamped()
        t.header.stamp = ts
        t.header.frame_id = self.map_frame_id
        t.child_frame_id = self.camera_frame_id
        t.transform.translation.x = pose.tx
        t.transform.translation.y = pose.ty
        t.transform.translation.z = pose.tz
        t.transform.rotation.x = pose.qx
        t.transform.rotation.y = pose.qy
        t.transform.rotation.z = pose.qz
        t.transform.rotation.w = pose.qw
        self.tf_broadcaster.sendTransform(t)

    def run(self):
        while not rospy.is_shutdown():
            got_frame = self.event.wait(timeout=0.5)  # Wait for a new frame

            if rospy.is_shutdown():
                break

            if got_frame:
                # Retrieve data from the stream
                depth = self.session.get_depth_frame()
                rgb = self.session.get_rgb_frame()
                confidence = self.session.get_confidence_frame()
                intrinsic_coeffs = self.session.get_intrinsic_mat()
                pose = self.session.get_camera_pose()
                now = rospy.Time.now()

                # The demo flips images from the TrueDepth camera, so we do the same.
                if self.session.get_device_type() == self.DEVICE_TYPE__TRUEDEPTH:
                    rgb = cv2.flip(rgb, 1)
                    depth = cv2.flip(depth, 1)
                    if confidence.size > 0:
                        confidence = cv2.flip(confidence, 1)

                # Publish all data
                self.publish_images(now, rgb, depth, confidence)
                self.publish_camera_info(now, intrinsic_coeffs, rgb.shape[1], rgb.shape[0])
                self.publish_transform(now, pose)

                self.event.clear()


if __name__ == "__main__":
    try:
        node = Record3DRosPublisher()
        node.run()
    except rospy.ROSInterruptException:
        pass
    except RuntimeError as e:
        rospy.logerr(f"Error while running the node: {e}")
