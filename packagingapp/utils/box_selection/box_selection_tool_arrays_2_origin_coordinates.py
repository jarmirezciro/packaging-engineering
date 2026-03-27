# -*- coding: utf-8 -*-
"""
Created on Wed Dec 14 10:30:37 2022

@author: a277008

"""

import pandas as pd


def box(l,a,h,lc,ac,hc,r1,r2,r3):
    b=[None]*6
    b_xyz=[None]*6
    a11=int(lc/l)
    a12=int(lc/a)
    a13=int(lc/h)
    a21=int(ac/l)
    a22=int(ac/a)
    a23=int(ac/h)
    a31=int(hc/l)
    a32=int(hc/a)
    a33=int(hc/h)
    
    b[0] = a11 * a22 * a33 * r3 # (l,a,h)
    b[1] = a11 * a32 * a23 * r2 # (l,h,a)
    b[2] = a21 * a12 * a33 * r3 # (a,l,h)
    b[3] = a31 * a12 * a23 * r1 # (a,h,l)
    b[4] = a31 * a22 * a13 * r1 # (h,a,l)
    b[5] = a21 * a32 * a13 * r2 # (h,l,a)
    
    b_xyz[0]=(l,a,h)
    b_xyz[1]=(l,h,a)
    b_xyz[2]=(a,l,h)
    b_xyz[3]=(a,h,l)
    b_xyz[4]=(h,a,l)
    b_xyz[5]=(h,l,a)
    
    calculated_box=max(b)
   
    max_position = b.index(calculated_box)  # The position (index) of the maximum value

    # Retrieve the corresponding arrays
    xyz = b_xyz[max_position]
    
    return calculated_box,  xyz




def MainBox(l,a,h,lc,ac,hc,r1,r2,r3,origin_coordinates):
    
    # --- MINIMAL SAFETY NORMALIZATION (NO LOGIC CHANGE) ---
    # Ensure flags are strictly 0/1 so the guards below behave predictably.
    r1 = 1 if r1 else 0
    r2 = 1 if r2 else 0
    r3 = 1 if r3 else 0
    
    p=[None]*3
    products=[None]*3
    box1=[None]*3
    nbox1=[None]*3
    nbox2=[None]*3
    nbox3=[None]*3
    nbox4=[None]*3
    nbox5=[None]*3
    nbox6=[None]*3
    bc=[None]*6
    b=[None]*6
    b_xyz=[None]*6
    coordinates_nbox1=[None]*3
    coordinates_nbox2=[None]*3
    coordinates_nbox3=[None]*3
    coordinates_nbox4=[None]*3
    coordinates_nbox5=[None]*3
    coordinates_nbox6=[None]*3
    dimensions_subbox=[None]*6
    
    nbox=[None]*6
    
    p[0]=l
    p[1]=a
    p[2]=h
    
    products[0] = l
    products[1] = a
    products[2] = h
    
    box1[0]=lc
    box1[1]=ac
    box1[2]=hc
    
    
    a11=int(lc/l)
    a12=int(lc/a)
    a13=int(lc/h)
    a21=int(ac/l)
    a22=int(ac/a)
    a23=int(ac/h)
    a31=int(hc/l)
    a32=int(hc/a)
    a33=int(hc/h)
    
    b[0] = a11 * a22 * a33
    b[1] = a11 * a32 * a23
    b[2] = a21 * a12 * a33
    b[3] = a31 * a12 * a23
    b[4] = a31 * a22 * a13
    b[5] = a21 * a32 * a13
    
    
    b_xyz[0]=(l,a,h)
    b_xyz[1]=(l,h,a)
    b_xyz[2]=(a,l,h)
    b_xyz[3]=(a,h,l)
    b_xyz[4]=(h,a,l)
    b_xyz[5]=(h,l,a)
    
    
    nbox1[0]=box1[0]-a11*products[0]
    nbox1[1]=box1[1]-a22*products[1]
    nbox1[2]=box1[2]-a33*products[2]
    
    coordinates_nbox1[0]=a11*products[0]
    coordinates_nbox1[1]=a22*products[1]
    coordinates_nbox1[2]=a33*products[2]
    
    nbox2[0]=box1[0]-a11*products[0]
    nbox2[1]=box1[1]-a23*products[2]
    nbox2[2]=box1[2]-a32*products[1]
    
    coordinates_nbox2[0]=a11*products[0]
    coordinates_nbox2[1]=a23*products[2]
    coordinates_nbox2[2]=a32*products[1]
    
    nbox3[0]=box1[0]-a12*products[1]
    nbox3[1]=box1[1]-a21*products[0]
    nbox3[2]=box1[2]-a33*products[2]
    
    coordinates_nbox3[0]=a12*products[1]
    coordinates_nbox3[1]=a21*products[0]
    coordinates_nbox3[2]=a33*products[2]
    
    
    nbox4[0]=box1[0]-a12*products[1]
    nbox4[1]=box1[1]-a23*products[2]
    nbox4[2]=box1[2]-a31*products[0]
    
    coordinates_nbox4[0]=a12*products[1]
    coordinates_nbox4[1]=a23*products[2]
    coordinates_nbox4[2]=a31*products[0]
    
    nbox5[0]=box1[0]-a13*products[2]
    nbox5[1]=box1[1]-a22*products[1]
    nbox5[2]=box1[2]-a31*products[0]
    
    coordinates_nbox5[0]=a13*products[2]
    coordinates_nbox5[1]=a22*products[1]
    coordinates_nbox5[2]=a31*products[0]
    
    
    nbox6[0]=box1[0]-a13*products[2]
    nbox6[1]=box1[1]-a21*products[0]
    nbox6[2]=box1[2]-a32*products[1]
    
    coordinates_nbox6[0]=a13*products[2]
    coordinates_nbox6[1]=a21*products[0]
    coordinates_nbox6[2]=a32*products[1]
    
    coordinates_subbox=[None]*6
    
    
    coordinates_subbox[0]=[(origin_coordinates[0], origin_coordinates[1]+coordinates_nbox1[1],origin_coordinates[2])
                    ,(origin_coordinates[0]+coordinates_nbox1[0],origin_coordinates[1],origin_coordinates[2])
                    ,(origin_coordinates[0], origin_coordinates[1],origin_coordinates[2]+coordinates_nbox1[2])]
    
    
    coordinates_subbox[1]=[(origin_coordinates[0], origin_coordinates[1]+coordinates_nbox2[1],origin_coordinates[2])
                    ,(origin_coordinates[0]+coordinates_nbox2[0],origin_coordinates[1],origin_coordinates[2])
                    ,(origin_coordinates[0], origin_coordinates[1],origin_coordinates[2]+coordinates_nbox2[2])]
    
    coordinates_subbox[2]=[(origin_coordinates[0], origin_coordinates[1]+coordinates_nbox3[1],origin_coordinates[2])
                    ,(origin_coordinates[0]+coordinates_nbox3[0],origin_coordinates[1],origin_coordinates[2])
                    ,(origin_coordinates[0], origin_coordinates[1],origin_coordinates[2]+coordinates_nbox3[2])]
    
    coordinates_subbox[3]=[(origin_coordinates[0], origin_coordinates[1]+coordinates_nbox4[1],origin_coordinates[2])
                    ,(origin_coordinates[0]+coordinates_nbox4[0],origin_coordinates[1],origin_coordinates[2])
                    ,(origin_coordinates[0], origin_coordinates[1],origin_coordinates[2]+coordinates_nbox4[2])]
    
    
    coordinates_subbox[4]=[(origin_coordinates[0], origin_coordinates[1]+coordinates_nbox5[1],origin_coordinates[2])
                    ,(origin_coordinates[0]+coordinates_nbox5[0],origin_coordinates[1],origin_coordinates[2])
                    ,(origin_coordinates[0], origin_coordinates[1],origin_coordinates[2]+coordinates_nbox5[2])]
    
    
    coordinates_subbox[5]=[(origin_coordinates[0], origin_coordinates[1]+coordinates_nbox6[1],origin_coordinates[2])
                    ,(origin_coordinates[0]+coordinates_nbox6[0],origin_coordinates[1],origin_coordinates[2])
                    ,(origin_coordinates[0], origin_coordinates[1],origin_coordinates[2]+coordinates_nbox6[2])]
    
    
    dimensions_subbox[0]=(a11*products[0],a22*products[1],a33*products[2])
    dimensions_subbox[1]=(a11*products[0],a23*products[2],a32*products[1])
    dimensions_subbox[2]=(a12*products[1],a21*products[0],a33*products[2])
    dimensions_subbox[3]=(a12*products[1],a23*products[2],a31*products[0])
    dimensions_subbox[4]=(a13*products[2],a22*products[1],a31*products[0])
    dimensions_subbox[5]=(a13*products[2],a21*products[0],a32*products[1])
   
    cl=[None]*6
    ca=[None]*6
    ch=[None]*6
    ca_xyz=[None]*6
    cl_xyz=[None]*6
    ch_xyz=[None]*6

    # --- ONLY CHANGE: replace "subbox(...) * rX" unpacking with guarded calls ---
    if r3:
        bc[0], cl[0],ca[0],ch[0],cl_xyz[0], ca_xyz[0], ch_xyz[0] = subbox(nbox1, box1, p, b[0], r1, r2, r3)
    else:
        bc[0] = 0
        cl[0] = [0, 0, 0]
        ca[0] = [0, 0, 0]
        ch[0] = [0, 0, 0]
        cl_xyz[0] = [0, 0, 0]
        ca_xyz[0] = [0, 0, 0]
        ch_xyz[0] = [0, 0, 0]

    if r2:
        bc[1], cl[1],ca[1],ch[1],cl_xyz[1], ca_xyz[1], ch_xyz[1] = subbox(nbox2, box1, p, b[1], r1, r2, r3)
    else:
        bc[1] = 0
        cl[1] = [0, 0, 0]
        ca[1] = [0, 0, 0]
        ch[1] = [0, 0, 0]
        cl_xyz[1] = [0, 0, 0]
        ca_xyz[1] = [0, 0, 0]
        ch_xyz[1] = [0, 0, 0]

    if r3:
        bc[2], cl[2],ca[2],ch[2],cl_xyz[2], ca_xyz[2], ch_xyz[2] = subbox(nbox3, box1, p, b[2], r1, r2, r3)
    else:
        bc[2] = 0
        cl[2] = [0, 0, 0]
        ca[2] = [0, 0, 0]
        ch[2] = [0, 0, 0]
        cl_xyz[2] = [0, 0, 0]
        ca_xyz[2] = [0, 0, 0]
        ch_xyz[2] = [0, 0, 0]

    if r1:
        bc[3], cl[3],ca[3],ch[3],cl_xyz[3], ca_xyz[3], ch_xyz[3] = subbox(nbox4, box1, p, b[3], r1, r2, r3)
    else:
        bc[3] = 0
        cl[3] = [0, 0, 0]
        ca[3] = [0, 0, 0]
        ch[3] = [0, 0, 0]
        cl_xyz[3] = [0, 0, 0]
        ca_xyz[3] = [0, 0, 0]
        ch_xyz[3] = [0, 0, 0]

    if r1:
        bc[4], cl[4],ca[4],ch[4],cl_xyz[4], ca_xyz[4], ch_xyz[4] = subbox(nbox5, box1, p, b[4], r1, r2, r3)
    else:
        bc[4] = 0
        cl[4] = [0, 0, 0]
        ca[4] = [0, 0, 0]
        ch[4] = [0, 0, 0]
        cl_xyz[4] = [0, 0, 0]
        ca_xyz[4] = [0, 0, 0]
        ch_xyz[4] = [0, 0, 0]

    if r2:
        bc[5], cl[5],ca[5],ch[5],cl_xyz[5], ca_xyz[5], ch_xyz[5] = subbox(nbox6, box1, p, b[5], r1, r2, r3)
    else:
        bc[5] = 0
        cl[5] = [0, 0, 0]
        ca[5] = [0, 0, 0]
        ch[5] = [0, 0, 0]
        cl_xyz[5] = [0, 0, 0]
        ca_xyz[5] = [0, 0, 0]
        ch_xyz[5] = [0, 0, 0]
    # --- END ONLY CHANGE ---

    max_quantity = max(bc)
    
    max_position = bc.index(max_quantity)
    
    # Retrieve the corresponding arrays
    cl_max=cl[max_position]
    ca_max=ca[max_position]
    ch_max=ch[max_position]
    
    cl_xyz_max=cl_xyz[max_position]
    ca_xyz_max=ca_xyz[max_position]
    ch_xyz_max=ch_xyz[max_position]
    
    coordinates_subbox_max=coordinates_subbox[max_position]
    
    dimensions_subbox_max=dimensions_subbox[max_position]
    
    b_xyz_max=b_xyz[max_position]
    
    return max_quantity, cl_max,ca_max, ch_max, cl_xyz_max, ca_xyz_max, ch_xyz_max, b_xyz_max, coordinates_subbox_max,dimensions_subbox_max



def subbox(nbox,box1,p,b,r1,r2,r3):
    
    #b=72
    cl1=[None]*3
    cl2=[None]*3
    cl3=[None]*3
    cl4=[None]*3
    cl5=[None]*3
    cl6=[None]*3
    
    ca1=[None]*3
    ca2=[None]*3
    ca3=[None]*3
    ca4=[None]*3
    ca5=[None]*3
    ca6=[None]*3
    
    ch1=[None]*3
    ch2=[None]*3
    ch3=[None]*3
    ch4=[None]*3
    ch5=[None]*3
    ch6=[None]*3
    
    bc=[None]*6
    
    array_data=[None]*6
 
#subbox1
    cl1[0] = box1[0]
    cl1[1] = nbox[1]
    cl1[2] = box1[2]
    ca1[0] = nbox[0]
    ca1[1] = box1[1] - nbox[1]
    ca1[2] = box1[2] - nbox[2]
    ch1[0] = box1[0]
    ch1[1] = box1[1] - nbox[1]
    ch1[2] = nbox[2]
   
#subbox2   
    cl2[0] = box1[0]
    cl2[1] = nbox[1]
    cl2[2] = box1[2]
    ca2[0] = nbox[0]
    ca2[1] = box1[1] - nbox[1]
    ca2[2] = box1[2]
    ch2[0] = box1[0] - nbox[0]
    ch2[1] = box1[1] - nbox[1]
    ch2[2] = nbox[2]
#subbox 3
    cl3[0] = box1[0] - nbox[0]
    cl3[1] = nbox[1]
    cl3[2] = box1[2] - nbox[2]
    ca3[0] = nbox[0]
    ca3[1] = box1[1]
    ca3[2] = box1[2] - nbox[2]
    ch3[0] = box1[0] - nbox[0]
    ch3[1] = box1[1]
    ch3[2] = nbox[2]
#subbox 4   
    cl4[0] = box1[0] - nbox[0]
    cl4[1] = nbox[1]
    cl4[2] = box1[2]
    ca4[0] = nbox[0]
    ca4[1] = box1[1]
    ca4[2] = box1[2]
    ch4[0] = box1[0] - nbox[0]
    ch4[1] = box1[1] - nbox[1]
    ch4[2] = nbox[2]
#subbox 5
    cl5[0] = box1[0] - nbox[0]
    cl5[1] = nbox[1]
    cl5[2] = box1[2] - nbox[2]
    ca5[0] = nbox[0]
    ca5[1] = box1[1]
    ca5[2] = box1[2] - nbox[2]
    ch5[0] = box1[0]
    ch5[1] = box1[1]
    ch5[2] = nbox[2]
#subbox 6
    cl6[0] = box1[0]
    cl6[1] = nbox[1]
    cl6[2] = box1[2] - nbox[2]
    ca6[0] = nbox[0]
    ca6[1] = box1[1] - nbox[1]
    ca6[2] = box1[2] - nbox[2]
    ch6[0] = box1[0]
    ch6[1] = box1[1]
    ch6[2] = nbox[2]
    
    
    array_data[0]=(cl1,ca1,ch1)
    array_data[1]=(cl2,ca2,ch2)
    array_data[2]=(cl3,ca3,ch3)
    array_data[3]=(cl4,ca4,ch4)
    array_data[4]=(cl5,ca5,ch5)
    array_data[5]=(cl6,ca6,ch6)
    
    
    quantitly_cl=[None]*6
    cl_xyz=[None]*6
    quantitly_ca=[None]*6
    ca_xyz=[None]*6
    quantitly_ch=[None]*6
    ch_xyz=[None]*6
    
    quantitly_cl[0], cl_xyz[0] = box(p[0], p[1], p[2], cl1[0], cl1[1], cl1[2], r1, r2, r3)
    quantitly_ca[0], ca_xyz[0] = box(p[0], p[1], p[2], ca1[0], ca1[1], ca1[2], r1, r2, r3)
    quantitly_ch[0], ch_xyz[0] = box(p[0], p[1], p[2], ch1[0], ch1[1], ch1[2], r1, r2, r3)
    
    quantitly_cl[1], cl_xyz[1] = box(p[0], p[1], p[2], cl2[0], cl2[1], cl2[2], r1, r2, r3)
    quantitly_ca[1], ca_xyz[1] = box(p[0], p[1], p[2], ca2[0], ca2[1], ca2[2], r1, r2, r3)
    quantitly_ch[1], ch_xyz[1] = box(p[0], p[1], p[2], ch2[0], ch2[1], ch2[2], r1, r2, r3)
    
    quantitly_cl[2], cl_xyz[2] = box(p[0], p[1], p[2], cl3[0], cl3[1], cl3[2], r1, r2, r3)
    quantitly_ca[2], ca_xyz[2] = box(p[0], p[1], p[2], ca3[0], ca3[1], ca3[2], r1, r2, r3)
    quantitly_ch[2], ch_xyz[2] = box(p[0], p[1], p[2], ch3[0], ch3[1], ch3[2], r1, r2, r3)
    
    quantitly_cl[3], cl_xyz[3] = box(p[0], p[1], p[2], cl4[0], cl4[1], cl4[2], r1, r2, r3)
    quantitly_ca[3], ca_xyz[3] = box(p[0], p[1], p[2], ca4[0], ca4[1], ca4[2], r1, r2, r3)
    quantitly_ch[3], ch_xyz[3] = box(p[0], p[1], p[2], ch4[0], ch4[1], ch4[2], r1, r2, r3)
    
    quantitly_cl[4], cl_xyz[4] = box(p[0], p[1], p[2], cl5[0], cl5[1], cl5[2], r1, r2, r3)
    quantitly_ca[4], ca_xyz[4] = box(p[0], p[1], p[2], ca5[0], ca5[1], ca5[2], r1, r2, r3)
    quantitly_ch[4], ch_xyz[4] = box(p[0], p[1], p[2], ch5[0], ch5[1], ch5[2], r1, r2, r3)
    
    quantitly_cl[5], cl_xyz[5] = box(p[0], p[1], p[2], cl6[0], cl6[1], cl6[2], r1, r2, r3)
    quantitly_ca[5], ca_xyz[5] = box(p[0], p[1], p[2], ca6[0], ca6[1], ca6[2], r1, r2, r3)
    quantitly_ch[5], ch_xyz[5] = box(p[0], p[1], p[2], ch6[0], ch6[1], ch6[2], r1, r2, r3)
    
    bc[0]= b+quantitly_cl[0]+quantitly_ca[0]+quantitly_ch[0]
    bc[1]= b+quantitly_cl[1]+quantitly_ca[1]+quantitly_ch[1]
    bc[2]= b+quantitly_cl[2]+quantitly_ca[2]+quantitly_ch[2]
    bc[3]= b+quantitly_cl[3]+quantitly_ca[3]+quantitly_ch[3]
    bc[4]= b+quantitly_cl[4]+quantitly_ca[4]+quantitly_ch[4]
    bc[5]= b+quantitly_cl[5]+quantitly_ca[5]+quantitly_ch[5]
    
    
    max_quantity = max(bc)
    
    max_position = bc.index(max_quantity)
    
    # Retrieve the corresponding arrays
    cl, ca, ch = array_data[max_position]
    
    cl_xyz_max=cl_xyz[max_position]
    ca_xyz_max=ca_xyz[max_position]
    ch_xyz_max=ch_xyz[max_position]
    
    return max_quantity, cl, ca, ch, cl_xyz_max, ca_xyz_max, ch_xyz_max



r1=1
r2=1
r3=1

lc=540
ac=365
hc=335

l=540
a=365
h=335


origin_coordinates=[None]*3
origin_coordinates[0]=0
origin_coordinates[1]=0
origin_coordinates[2]=0



l=13
a=7
h=3

lc=50
ac=30
hc=20



r1=1
r2=1
r3=1



max_quantity, cl_max,ca_max, ch_max, cl_xyz_max, ca_xyz_max, ch_xyz_max, b_xyz_max, coordinates_subbox_max,dimensions_subbox_max=MainBox(l,a,h,lc,ac,hc,r1,r2,r3,origin_coordinates)


MainBox(l,a,h,dimensions_subbox_max[0],dimensions_subbox_max[1],dimensions_subbox_max[2],r1,r2,r3,origin_coordinates)
MainBox(l,a,h,cl_max[0],cl_max[1],cl_max[2],r1,r2,r3,coordinates_subbox_max[0])
MainBox(l,a,h,ca_max[0],ca_max[1],ca_max[2],r1,r2,r3,coordinates_subbox_max[1])
MainBox(l,a,h,ch_max[0],ch_max[1],ch_max[2],r1,r2,r3,coordinates_subbox_max[2])



"""
MainBox(l,a,h,lc,ac,hc,r1,r2,r3)


result = MainBox(l=2, a=3, h=4, lc=10, ac=8, hc=6, r1=1, r2=1, r3=1)
print("Maximum packed boxes:", result)




branding="Volvo"



df_box_list=pd.read_excel("cardboard_box_list.xlsx")
df_box_list.sort_values(by=['Volume (mm3)'],ascending=True, inplace=True)
desired_quantity_per_carton=1

def multi_product_box_selection(l,a,h,df_box_list,desired_quantity_per_carton,branding):
    r1=1
    r2=1
    r3=1
    
    if branding=="Branded Packaging":
        branding="Volvo"
    else: branding="BNP"
    
    if not l or l == 0 or pd.isna(l) or not a or a == 0 or pd.isna(a) or not h or h == 0 or pd.isna(h):
        best_box = "INCOMPLETE DIMENSIONS"
        return best_box

    
    try:
        df_box_list['Max Qty per Carton']=df_box_list.apply(lambda row : MainBox(l,a,h,row['Lenght (mm)'],row['Width (mm)'],row['Height (mm)'],r1,r2,r3),axis=1)
        df_box_list['% Usage']=desired_quantity_per_carton*((l*a*h)/df_box_list['Volume (mm3)'])
        df_result=df_box_list.loc[(df_box_list['% Usage']<=1) &(df_box_list['Max Qty per Carton']>=desired_quantity_per_carton) & (str(df_box_list['Branding'])==branding)]
        df_result=df_box_list.loc[(df_box_list['% Usage']<=1) & (df_box_list['Max Qty per Carton']>=desired_quantity_per_carton)]
        #https://stackoverflow.com/questions/64108365/extract-value-based-on-max-value-pandas-dataframe
        best_box = df_result.loc[df_result['% Usage'].idxmax()]
        best_box=best_box['Part Number']
    except:
        best_box='NO BOXES SUITS THE REQUIREMENTS'
    
    return best_box

best_box=multi_product_box_selection(l,a,h,df_box_list,desired_quantity_per_carton,branding)
    
    """
