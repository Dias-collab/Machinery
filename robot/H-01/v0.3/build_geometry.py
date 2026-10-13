"""Reproducible conceptual H-01 geometry. Not manufacturing or dynamics data."""
import csv, json, math, shutil
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
params = []
def par(name, value, unit='mm', source='user_v03', category='numerical_assumption'):
    params.append(dict(parameter_id=name, value=value, unit=unit, status='proposed',
                       category=category, source=source, revision='0.3', tolerance='', verification_required='yes'))
for n,v in [('H',1600),('B_hip',90),('L_thigh',400),('L_shank',390),('H_ankle',85),
            ('B_feet',180),('L_foot',250),('W_foot',110),('L_upper_arm',280),('L_forearm',250)]:
    par(n,v)
for n,v in [('B_shoulder',225),('H_shoulder_ground',1290),('H_waist_above_base',100),
            ('H_neck_ground',1400),('L_tcp',160),('ankle_to_heel',85),('gripper_stroke',40)]:
    par(n,v,source='editor_placeholder_not_approved',category='layout_to_verify')
par('body_coordinates',28,'count',category='working_architecture')
par('gripper_coordinates',2,'count',category='working_architecture')
for group in ['hip','shoulder','ankle','neck','waist','wrist']:
    for stage in ['stage2','stage3']:
        for ax in 'xyz':
            par(f'{group}_{stage}_d{ax}',0,source='idealized_zero_NOT_actual_coincidence',category='layout_to_verify')

def values(): return {p['parameter_id']: float(p['value']) for p in params}
P=values()
base_height=P['H_ankle']+P['L_shank']+P['L_thigh']
par('H_base_ground',base_height,source='H_ankle+L_shank+L_thigh_only_zero_offsets')

joints=[]
def joint(name,parent,child,xyz=(0,0,0),axis=(0,0,1),limits=(-90,90),kind='revolute',offset='',expression=''):
    row=dict(joint_id=name,parent_link=parent,child_link=child,joint_type=kind,
             origin_x_mm=xyz[0],origin_y_mm=xyz[1],origin_z_mm=xyz[2],
             origin_roll_deg=0,origin_pitch_deg=0,origin_yaw_deg=0,
             axis_x=axis[0],axis_y=axis[1],axis_z=axis[2],
             limit_lower=limits[0],limit_upper=limits[1],limit_unit='deg' if kind=='revolute' else 'mm',
             zero_offset='',zero_offset_status='unknown_encoder_calibration',
             actuator_envelope='' if kind=='fixed' else 'ENV_'+name,
             origin_expression=expression,offset_prefix=offset,status='proposed_idealized')
    if offset:
        row['origin_expression']=';'.join(f'{offset}_d{a}' for a in 'xyz')
        for a in 'xyz': row[f'origin_{a}_mm']+=P[f'{offset}_d{a}']
    joints.append(row)
    return child

# The first entries define pelvis-to-feet chains. All zero frames share base orientation.
for side,s in [('left',1),('right',-1)]:
    pre=side+'_'
    a=joint(pre+'hip_yaw','base_link',pre+'hip_yaw_link',(0,s*P['B_hip'],0),limits=(-45,45),expression=f'0;{s}*B_hip;0')
    b=joint(pre+'hip_roll',a,pre+'hip_roll_link',axis=(1,0,0),limits=(-35,35),offset='hip_stage2')
    c=joint(pre+'hip_pitch',b,pre+'thigh',axis=(0,-1,0),limits=(-40,90),offset='hip_stage3')
    d=joint(pre+'knee_pitch',c,pre+'shank',(0,0,-P['L_thigh']),axis=(0,1,0),limits=(0,130),expression='0;0;-L_thigh')
    e=joint(pre+'ankle_pitch',d,pre+'ankle_pitch_link',(0,0,-P['L_shank']),axis=(0,-1,0),limits=(-30,45),expression='0;0;-L_shank')
    f=joint(pre+'ankle_roll',e,pre+'foot',axis=(1,0,0),limits=(-25,25),offset='ankle_stage2')
    joint(pre+'sole_fixed',f,pre+'sole',(0,0,-P['H_ankle']),kind='fixed',limits=(0,0),expression='0;0;-H_ankle')
a=joint('waist_yaw','base_link','waist_yaw_link',(0,0,P['H_waist_above_base']),limits=(-45,45),expression='0;0;H_waist_above_base')
torso=joint('waist_pitch',a,'torso',axis=(0,1,0),limits=(-25,35),offset='waist_stage2')
neck_h=P['H_neck_ground']-base_height-P['H_waist_above_base']
a=joint('neck_yaw',torso,'neck_yaw_link',(0,0,neck_h),limits=(-70,70),expression='0;0;H_neck_ground-H_base_ground-H_waist_above_base')
joint('neck_pitch',a,'head',axis=(0,1,0),limits=(-40,45),offset='neck_stage2')
for side,s in [('left',1),('right',-1)]:
    pre=side+'_'
    sh=P['H_shoulder_ground']-base_height-P['H_waist_above_base']
    a=joint(pre+'shoulder_yaw',torso,pre+'shoulder_yaw_link',(0,s*P['B_shoulder'],sh),limits=(-90,90),expression=f'0;{s}*B_shoulder;H_shoulder_ground-H_base_ground-H_waist_above_base')
    b=joint(pre+'shoulder_roll',a,pre+'shoulder_roll_link',axis=(1,0,0),limits=(-90,90),offset='shoulder_stage2')
    c=joint(pre+'shoulder_pitch',b,pre+'upper_arm',axis=(0,-1,0),limits=(-90,135),offset='shoulder_stage3')
    d=joint(pre+'elbow_pitch',c,pre+'forearm',(0,0,-P['L_upper_arm']),axis=(0,-1,0),limits=(0,135),expression='0;0;-L_upper_arm')
    e=joint(pre+'forearm_roll',d,pre+'forearm_roll_link',(0,0,-P['L_forearm']),axis=(0,0,-1),limits=(-90,90),expression='0;0;-L_forearm')
    f=joint(pre+'wrist_pitch',e,pre+'gripper_body',axis=(0,-1,0),limits=(-60,60),offset='wrist_stage2')
    joint(pre+'tcp_fixed',f,pre+'tcp',(0,0,-P['L_tcp']),kind='fixed',limits=(0,0),expression='0;0;-L_tcp')
    # One equivalent slider, not a detailed parallel-finger gripper mechanism.
    joint(pre+'gripper_closure',f,pre+'gripper_slider',axis=(0,s,0),kind='prismatic',limits=(0,P['gripper_stroke']))

def write_csv(name,rows):
    with (DATA/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write_csv('parameters.csv',params)
write_csv('joints.csv',joints)
links=[dict(link_id='base_link',parent_joint_id='',geometry_ref='',length_mm='',
            mass_kg='',com_xyz='',inertia_tensor='',collision_ref='',status='geometry_only_no_mass')]
for j in joints:
    name=j['child_link'];length=''
    for suffix,param in [('thigh','L_thigh'),('shank','L_shank'),('upper_arm','L_upper_arm'),('forearm','L_forearm'),('foot','L_foot')]:
        if name.endswith('_'+suffix):length=P[param]
    links.append(dict(link_id=name,parent_joint_id=j['joint_id'],geometry_ref='',length_mm=length,
                      mass_kg='',com_xyz='',inertia_tensor='',collision_ref='',status='geometry_only_no_mass'))
write_csv('links.csv',links)

tests=[]
descs=[('T01','Нулевая стойка','all_zero'),('T02','Рабочая стойка','hips_10_knees_20_ankles_10_deg'),
       ('T03','Подбор с подставки 600 мм',''),('T04','Передача на высоте 1100 мм',''),
       ('T05','Перенос 1 кг',''),('T06','Шаг 200 мм',''),('T07','Подъём стопы 50 мм',''),('T08','Перенос веса на одну ногу','')]
for tid,desc,config in descs:
    q={j['joint_id']:0 for j in joints if j['joint_type']!='fixed'} if config else {}
    if tid=='T02':
        for side in ['left','right']:
            for j,v in [('hip_pitch',10),('knee_pitch',20),('ankle_pitch',10)]:q[side+'_'+j]=v
    tests.append(dict(pose_id=tid,description=desc,joint_positions=json.dumps(q),joint_units='deg_and_mm',
                      tcp_target='UNDEFINED' if tid in ['T03','T04','T05'] else '',
                      support_contacts='left_sole;right_sole' if tid in ['T01','T02','T03','T04','T05'] else 'UNDEFINED',
                      object_mass=1 if tid=='T05' else '',trajectory_ref='',
                      acceptance_criteria='limits;collisions;TCP_orientation;contact;path;criteria_not_quantified',
                      status='NOT_TESTED'))
write_csv('test_poses.csv',tests)

# Zero-pose FK: all joint origin rotations are identity by this specific convention.
positions={'base_link':(0,0,0)}
pending=list(joints)
while pending:
    ready=[j for j in pending if j['parent_link'] in positions]
    if not ready:raise ValueError('Cycle or disconnected links')
    for j in ready:
        positions[j['child_link']]=tuple(positions[j['parent_link']][i]+j[f'origin_{a}_mm'] for i,a in enumerate('xyz'))
        pending.remove(j)
coords=[]
for j in joints:
    p=positions[j['child_link']]
    coords.append(dict(joint_id=j['joint_id'],joint_type=j['joint_type'],x_base_mm=p[0],y_base_mm=p[1],z_base_mm=p[2],
                       x_ground_mm=p[0],y_ground_mm=p[1],z_ground_mm=p[2]+base_height,
                       axis_x_base=j['axis_x'],axis_y_base=j['axis_y'],axis_z_base=j['axis_z'],status='idealized_zero_pose'))
write_csv('joint_coordinates.csv',coords)

robot=ET.Element('robot',name='H01_v03_idealized')
for link in links:ET.SubElement(robot,'link',name=link['link_id'])
for j in joints:
    node=ET.SubElement(robot,'joint',name=j['joint_id'],type=j['joint_type'])
    ET.SubElement(node,'parent',link=j['parent_link']);ET.SubElement(node,'child',link=j['child_link'])
    ET.SubElement(node,'origin',xyz=' '.join(str(j[f'origin_{a}_mm']/1000) for a in 'xyz'),rpy='0 0 0')
    if j['joint_type']!='fixed':
        ET.SubElement(node,'axis',xyz=' '.join(str(j[f'axis_{a}']) for a in 'xyz'))
        # Parser-required values are placeholders, explicitly not ratings.
        scale=math.pi/180 if j['joint_type']=='revolute' else .001
        ET.SubElement(node,'limit',lower=str(j['limit_lower']*scale),upper=str(j['limit_upper']*scale),effort='1',velocity='0.1')
ET.indent(robot)
ET.ElementTree(robot).write(ROOT/'H01_geometry_only.urdf',encoding='utf-8',xml_declaration=True)

active=[j for j in joints if j['joint_type']!='fixed']
assert len(active)==30
assert len({j['joint_id'] for j in joints})==len(joints)
assert len({j['child_link'] for j in joints})==len(joints)
assert all(abs(sum(j[f'axis_{a}']**2 for a in 'xyz')-1)<1e-12 for j in active)
assert all(j['limit_lower']<=j['limit_upper'] for j in active)
assert len(positions)==len(links)
assert positions['left_sole'][2]+base_height==0
assert positions['right_sole'][2]+base_height==0
drop=P['L_thigh']*math.cos(math.radians(10))+P['L_shank']*math.cos(math.radians(10))+P['H_ankle']
shift=(P['L_thigh']-P['L_shank'])*math.sin(math.radians(10))
report={'revision':'0.3','active_coordinates':len(active),'revolute_body':28,'equivalent_gripper_sliders':2,
        'fixed_joints':len(joints)-len(active),'links':len(links),'tree':'PASS_connected_single_parent',
        'axes':'PASS_unit_vectors','limits':'PASS_order_only_not_mechanical_verification',
        'zero_sole_height_ground_mm':0,'base_height_zero_mm':base_height,
        'work_pose_base_height_mm':drop,'work_pose_sole_x_relative_base_mm':shift,
        'T01':'sole_geometry_checked_no_collision_geometry',
        'T02':'sagittal_analytical_check_only_no_load_or_collision_check',
        'T03_T08':'NOT_VERIFIED_missing_targets_trajectories_mass_collision_geometry',
        'CAD_ready':'NO_offsets_and_envelopes_unverified',
        'URDF':'geometry_only_effort_1_velocity_0.1_placeholder_NOT_control_or_dynamics'}
(ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
tree=['base_link']
def walk(parent,indent):
    for j in joints:
        if j['parent_link']==parent:
            tree.append(' '*indent+j['joint_id']+' -> '+j['child_link']);walk(j['child_link'],indent+2)
walk('base_link',2)
(ROOT/'kinematic_tree.txt').write_text('\n'.join(tree),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
