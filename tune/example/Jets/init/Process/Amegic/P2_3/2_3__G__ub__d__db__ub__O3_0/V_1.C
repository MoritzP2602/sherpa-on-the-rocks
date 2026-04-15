#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M20()
{
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M21()
{
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M22()
{
  M[22][1] = (Z[18]*Z[110]+Z[16]*Z[109])*Z[21];
  M[22][2] = -(Z[71]*Z[106]+Z[70]*Z[105])*Z[28];
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M23()
{
  M[23][1] = Z[21]*Z[49]*Z[110];
  M[23][2] = -Z[28]*Z[72]*Z[105];
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M24()
{
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M25()
{
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M26()
{
  M[26][1] = Z[21]*Z[74]*Z[103];
  M[26][2] = -Z[28]*Z[25]*Z[112];
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M27()
{
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M28()
{
  M[28][3] = Z[35]*Z[93]*Z[84];
  M[28][4] = -Z[42]*Z[39]*Z[114];
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M29()
{
  M[29][3] = (Z[98]*Z[85]+Z[97]*Z[84])*Z[35];
  M[29][4] = -(Z[58]*Z[114]+Z[57]*Z[113])*Z[42];
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M30()
{
  M[30][0] = Z[115]*Z[14];
  M[30][1] = -Z[21]*Z[19]*Z[92];
  M[30][2] = (Z[26]*Z[92]-Z[71]*Z[112])*Z[28];
  M[30][3] = -Z[35]*Z[33]*Z[92];
  M[30][4] = -Z[42]*Z[64]*Z[114];
}

void V2_3__G__ub__d__db__ub__O3_0::Calculate_M31()
{
  M[31][0] = Z[116]*Z[14];
  M[31][1] = -(Z[50]*Z[92]-Z[79]*Z[110])*Z[21];
  M[31][2] = Z[28]*Z[53]*Z[92];
  M[31][3] = -(Z[56]*Z[92]-Z[98]*Z[91])*Z[35];
  M[31][4] = -Z[42]*Z[59]*Z[92];
}

