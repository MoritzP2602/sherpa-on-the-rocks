#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__d__db__G__u__ub__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__d__db__G__u__ub__O3_0(bs);
}

V2_3__d__db__G__u__ub__O3_0::V2_3__d__db__G__u__ub__O3_0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Xfunc(0,_BS),
     Basic_Vfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[3];
  c = new Complex[4];
  Z = new Complex[121];
  M = new Complex*[32];
  for(int i=0;i<32;i++) M[i] = new Complex[5];
  cl = new int[32];
}

V2_3__d__db__G__u__ub__O3_0::~V2_3__d__db__G__u__ub__O3_0()
{
  if (Z)  delete[] Z;
  if (f)  delete[] f;
  if (c)  delete[] c;
  if (cl) delete[] cl;
  if (M) {
    for(int i=0;i<32;i++) delete[] M[i];
    delete[] M;
  }
}

Complex V2_3__d__db__G__u__ub__O3_0::Evaluate(int m,int n)
{
  if (cl[n]) return M[n][m];
  switch (n) {
    case 0: Calculate_M0(); break;
    case 1: Calculate_M1(); break;
    case 2: Calculate_M2(); break;
    case 3: Calculate_M3(); break;
    case 4: Calculate_M4(); break;
    case 5: Calculate_M5(); break;
    case 6: Calculate_M6(); break;
    case 7: Calculate_M7(); break;
    case 8: Calculate_M8(); break;
    case 9: Calculate_M9(); break;
    case 10: Calculate_M10(); break;
    case 11: Calculate_M11(); break;
    case 12: Calculate_M12(); break;
    case 13: Calculate_M13(); break;
    case 14: Calculate_M14(); break;
    case 15: Calculate_M15(); break;
    case 16: Calculate_M16(); break;
    case 17: Calculate_M17(); break;
    case 18: Calculate_M18(); break;
    case 19: Calculate_M19(); break;
    case 20: Calculate_M20(); break;
    case 21: Calculate_M21(); break;
    case 22: Calculate_M22(); break;
    case 23: Calculate_M23(); break;
    case 24: Calculate_M24(); break;
    case 25: Calculate_M25(); break;
    case 26: Calculate_M26(); break;
    case 27: Calculate_M27(); break;
    case 28: Calculate_M28(); break;
    case 29: Calculate_M29(); break;
    case 30: Calculate_M30(); break;
    case 31: Calculate_M31(); break;
  }
  cl[n]=1;
  return M[n][m];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M0()
{
  M[0][0] = (Z[5]*Z[4]-Z[2]*Z[1])*Z[9];
  M[0][1] = -Z[19]*Z[21];
  M[0][2] = -Z[26]*Z[1]*Z[24];
  M[0][3] = (Z[1]*Z[27]+Z[29]*Z[28])*Z[31];
  M[0][4] = Z[38]*Z[1]*Z[35];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M1()
{
  M[1][0] = (Z[39]*Z[4]-Z[2]*Z[3])*Z[9];
  M[1][1] = -Z[44]*Z[21];
  M[1][2] = -Z[26]*Z[3]*Z[24];
  M[1][3] = (Z[3]*Z[27]+Z[46]*Z[28])*Z[31];
  M[1][4] = Z[38]*Z[3]*Z[35];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M2()
{
  M[2][0] = -Z[9]*Z[2]*Z[36];
  M[2][1] = -Z[54]*Z[21];
  M[2][2] = -Z[26]*Z[36]*Z[24];
  M[2][3] = (Z[36]*Z[27]+Z[56]*Z[28])*Z[31];
  M[2][4] = -(Z[34]*Z[57]-Z[36]*Z[35])*Z[38];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M3()
{
  M[3][0] = -Z[9]*Z[2]*Z[49];
  M[3][1] = -Z[61]*Z[21];
  M[3][2] = -Z[26]*Z[49]*Z[24];
  M[3][3] = (Z[49]*Z[27]+Z[63]*Z[28])*Z[31];
  M[3][4] = -(Z[48]*Z[57]-Z[49]*Z[35])*Z[38];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M4()
{
  M[4][0] = -Z[9]*Z[64]*Z[1];
  M[4][1] = -Z[71]*Z[21];
  M[4][2] = -(Z[23]*Z[72]+Z[1]*Z[73])*Z[26];
  M[4][3] = Z[31]*Z[1]*Z[74];
  M[4][4] = -(Z[33]*Z[76]-Z[1]*Z[77])*Z[38];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M5()
{
  M[5][0] = -Z[9]*Z[64]*Z[3];
  M[5][1] = -Z[81]*Z[21];
  M[5][2] = -(Z[45]*Z[72]+Z[3]*Z[73])*Z[26];
  M[5][3] = Z[31]*Z[3]*Z[74];
  M[5][4] = -(Z[47]*Z[76]-Z[3]*Z[77])*Z[38];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M6()
{
  M[6][0] = (Z[66]*Z[50]-Z[64]*Z[36])*Z[9];
  M[6][1] = -Z[83]*Z[21];
  M[6][2] = -(Z[55]*Z[72]+Z[36]*Z[73])*Z[26];
  M[6][3] = Z[31]*Z[36]*Z[74];
  M[6][4] = Z[38]*Z[36]*Z[77];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M7()
{
  M[7][0] = (Z[79]*Z[50]-Z[64]*Z[49])*Z[9];
  M[7][1] = -Z[86]*Z[21];
  M[7][2] = -(Z[62]*Z[72]+Z[49]*Z[73])*Z[26];
  M[7][3] = Z[31]*Z[49]*Z[74];
  M[7][4] = Z[38]*Z[49]*Z[77];
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M8()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M9()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M10()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M11()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M12()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M13()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M14()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M15()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M16()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M17()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M18()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M19()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M20()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M21()
{
}

void V2_3__d__db__G__u__ub__O3_0::Calculate_M22()
{
}

