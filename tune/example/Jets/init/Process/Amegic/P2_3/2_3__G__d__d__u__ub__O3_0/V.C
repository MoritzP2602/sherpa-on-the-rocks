#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__G__d__d__u__ub__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__G__d__d__u__ub__O3_0(bs);
}

V2_3__G__d__d__u__ub__O3_0::V2_3__G__d__d__u__ub__O3_0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Xfunc(0,_BS),
     Basic_Vfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[3];
  c = new Complex[4];
  Z = new Complex[117];
  M = new Complex*[32];
  for(int i=0;i<32;i++) M[i] = new Complex[5];
  cl = new int[32];
}

V2_3__G__d__d__u__ub__O3_0::~V2_3__G__d__d__u__ub__O3_0()
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

Complex V2_3__G__d__d__u__ub__O3_0::Evaluate(int m,int n)
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

void V2_3__G__d__d__u__ub__O3_0::Calculate_M0()
{
  M[0][0] = -Z[11]*Z[14];
  M[0][1] = -Z[21]*Z[16]*Z[15];
  M[0][2] = -Z[28]*Z[26]*Z[4];
  M[0][3] = (Z[33]*Z[4]-Z[30]*Z[29])*Z[35];
  M[0][4] = -Z[42]*Z[40]*Z[4];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M1()
{
  M[1][0] = -Z[47]*Z[14];
  M[1][1] = -Z[21]*Z[50]*Z[4];
  M[1][2] = -(Z[53]*Z[4]-Z[51]*Z[22])*Z[28];
  M[1][3] = Z[35]*Z[56]*Z[4];
  M[1][4] = -(Z[59]*Z[4]-Z[57]*Z[36])*Z[42];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M2()
{
  M[2][1] = -Z[21]*Z[60]*Z[15];
  M[2][2] = Z[28]*Z[25]*Z[63];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M3()
{
  M[3][1] = -(Z[66]*Z[17]+Z[65]*Z[15])*Z[21];
  M[3][2] = (Z[52]*Z[63]+Z[51]*Z[62])*Z[28];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M4()
{
  M[4][1] = -(Z[18]*Z[68]+Z[16]*Z[67])*Z[21];
  M[4][2] = (Z[70]*Z[24]+Z[69]*Z[22])*Z[28];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M5()
{
  M[5][1] = -Z[21]*Z[49]*Z[68];
  M[5][2] = Z[28]*Z[71]*Z[22];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M6()
{
  M[6][0] = -Z[76]*Z[14];
  M[6][1] = -Z[21]*Z[19]*Z[64];
  M[6][2] = -(Z[26]*Z[64]-Z[70]*Z[63])*Z[28];
  M[6][3] = (Z[33]*Z[64]-Z[30]*Z[77])*Z[35];
  M[6][4] = -Z[42]*Z[40]*Z[64];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M7()
{
  M[7][0] = -Z[82]*Z[14];
  M[7][1] = -Z[21]*Z[66]*Z[68];
  M[7][2] = -Z[28]*Z[53]*Z[64];
  M[7][3] = Z[35]*Z[56]*Z[64];
  M[7][4] = -(Z[59]*Z[64]-Z[57]*Z[79])*Z[42];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M8()
{
  M[8][3] = -(Z[32]*Z[84]+Z[30]*Z[83])*Z[35];
  M[8][4] = (Z[87]*Z[38]+Z[86]*Z[36])*Z[42];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M9()
{
  M[9][3] = -Z[35]*Z[55]*Z[84];
  M[9][4] = Z[42]*Z[88]*Z[36];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M10()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M11()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M12()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M13()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M14()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M15()
{
  M[15][3] = -Z[35]*Z[55]*Z[91];
  M[15][4] = Z[42]*Z[88]*Z[79];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M16()
{
  M[16][3] = -Z[35]*Z[93]*Z[29];
  M[16][4] = Z[42]*Z[39]*Z[96];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M17()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M18()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M19()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M20()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M21()
{
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M22()
{
  M[22][3] = -Z[35]*Z[93]*Z[77];
  M[22][4] = Z[42]*Z[39]*Z[100];
}

void V2_3__G__d__d__u__ub__O3_0::Calculate_M23()
{
  M[23][3] = -(Z[98]*Z[78]+Z[97]*Z[77])*Z[35];
  M[23][4] = (Z[58]*Z[100]+Z[57]*Z[99])*Z[42];
}

