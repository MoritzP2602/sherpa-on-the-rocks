#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;

void V2_3__G__db__u__db__ub__O3_0::Calculate_M22()
{
  M[22][1] = -(Z[18]*Z[110]+Z[16]*Z[109])*Z[21];
  M[22][2] = (Z[64]*Z[106]+Z[63]*Z[105])*Z[28];
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M23()
{
  M[23][1] = -Z[21]*Z[49]*Z[110];
  M[23][2] = Z[28]*Z[65]*Z[105];
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M24()
{
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M25()
{
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M26()
{
  M[26][3] = -Z[35]*Z[93]*Z[84];
  M[26][4] = Z[42]*Z[39]*Z[112];
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M27()
{
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M28()
{
  M[28][1] = -Z[21]*Z[74]*Z[103];
  M[28][2] = Z[28]*Z[25]*Z[114];
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M29()
{
  M[29][1] = -(Z[79]*Z[104]+Z[78]*Z[103])*Z[21];
  M[29][2] = (Z[52]*Z[114]+Z[51]*Z[113])*Z[28];
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M30()
{
  M[30][0] = -Z[115]*Z[14];
  M[30][1] = Z[21]*Z[19]*Z[92];
  M[30][2] = Z[28]*Z[64]*Z[114];
  M[30][3] = Z[35]*Z[33]*Z[92];
  M[30][4] = -(Z[40]*Z[92]-Z[71]*Z[112])*Z[42];
}

void V2_3__G__db__u__db__ub__O3_0::Calculate_M31()
{
  M[31][0] = -Z[116]*Z[14];
  M[31][1] = (Z[50]*Z[92]-Z[79]*Z[110])*Z[21];
  M[31][2] = Z[28]*Z[53]*Z[92];
  M[31][3] = (Z[56]*Z[92]-Z[98]*Z[91])*Z[35];
  M[31][4] = -Z[42]*Z[59]*Z[92];
}

