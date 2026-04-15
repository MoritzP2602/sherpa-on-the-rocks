#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__G__db__d__db__db__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__G__db__d__db__db__O3_0(bs);
}

V2_3__G__db__d__db__db__O3_0::V2_3__G__db__d__db__db__O3_0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Xfunc(0,_BS),
     Basic_Vfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[2];
  c = new Complex[4];
  Z = new Complex[188];
  M = new Complex*[32];
  for(int i=0;i<32;i++) M[i] = new Complex[10];
  cl = new int[32];
}

V2_3__G__db__d__db__db__O3_0::~V2_3__G__db__d__db__db__O3_0()
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

Complex V2_3__G__db__d__db__db__O3_0::Evaluate(int m,int n)
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

void V2_3__G__db__d__db__db__O3_0::Calculate_M0()
{
  M[0][0] = -Z[11]*Z[14];
  M[0][1] = Z[24]*Z[27];
  M[0][2] = -(Z[32]*Z[17]-Z[29]*Z[28])*Z[34];
  M[0][3] = Z[41]*Z[39]*Z[17];
  M[0][4] = (Z[32]*Z[4]-Z[29]*Z[42])*Z[44];
  M[0][5] = Z[51]*Z[49]*Z[4];
  M[0][6] = (Z[56]*Z[4]-Z[53]*Z[52])*Z[58];
  M[0][7] = -Z[61]*Z[39]*Z[4];
  M[0][8] = -(Z[56]*Z[17]-Z[53]*Z[62])*Z[64];
  M[0][9] = -Z[67]*Z[49]*Z[17];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M1()
{
  M[1][0] = -Z[72]*Z[14];
  M[1][1] = Z[77]*Z[27];
  M[1][2] = -Z[34]*Z[80]*Z[17];
  M[1][3] = (Z[83]*Z[17]-Z[81]*Z[35])*Z[41];
  M[1][4] = Z[44]*Z[80]*Z[4];
  M[1][5] = Z[51]*Z[84]*Z[45];
  M[1][6] = Z[58]*Z[89]*Z[4];
  M[1][7] = -(Z[83]*Z[4]-Z[81]*Z[59])*Z[61];
  M[1][8] = -Z[64]*Z[89]*Z[17];
  M[1][9] = -Z[67]*Z[84]*Z[65];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M2()
{
  M[2][4] = -(Z[31]*Z[91]+Z[29]*Z[90])*Z[44];
  M[2][5] = (Z[94]*Z[47]+Z[93]*Z[45])*Z[51];
  M[2][8] = (Z[55]*Z[96]+Z[53]*Z[95])*Z[64];
  M[2][9] = -(Z[94]*Z[66]+Z[93]*Z[65])*Z[67];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M3()
{
  M[3][4] = -Z[44]*Z[79]*Z[91];
  M[3][5] = Z[51]*Z[98]*Z[45];
  M[3][8] = Z[64]*Z[88]*Z[96];
  M[3][9] = -Z[67]*Z[98]*Z[65];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M4()
{
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M5()
{
  M[5][2] = Z[34]*Z[79]*Z[101];
  M[5][3] = -Z[41]*Z[108]*Z[35];
  M[5][6] = -Z[58]*Z[88]*Z[106];
  M[5][7] = Z[61]*Z[108]*Z[59];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M6()
{
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M7()
{
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M8()
{
  M[8][2] = Z[34]*Z[110]*Z[28];
  M[8][3] = -Z[41]*Z[38]*Z[113];
  M[8][4] = -Z[44]*Z[110]*Z[42];
  M[8][5] = Z[51]*Z[48]*Z[115];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M9()
{
  M[9][2] = (Z[117]*Z[30]+Z[116]*Z[28])*Z[34];
  M[9][3] = -(Z[82]*Z[113]+Z[81]*Z[112])*Z[41];
  M[9][4] = -(Z[117]*Z[43]+Z[116]*Z[42])*Z[44];
  M[9][5] = (Z[85]*Z[115]+Z[84]*Z[114])*Z[51];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M10()
{
  M[10][0] = -Z[121]*Z[14];
  M[10][4] = Z[44]*Z[32]*Z[92];
  M[10][5] = Z[51]*Z[94]*Z[115];
  M[10][6] = (Z[56]*Z[92]-Z[53]*Z[122])*Z[58];
  M[10][7] = -Z[61]*Z[39]*Z[92];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M11()
{
  M[11][0] = -Z[127]*Z[14];
  M[11][4] = (Z[80]*Z[92]-Z[117]*Z[91])*Z[44];
  M[11][5] = Z[51]*Z[86]*Z[92];
  M[11][6] = Z[58]*Z[89]*Z[92];
  M[11][7] = -(Z[83]*Z[92]-Z[81]*Z[124])*Z[61];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M12()
{
  M[12][1] = Z[131]*Z[27];
  M[12][2] = -Z[34]*Z[32]*Z[102];
  M[12][3] = (Z[39]*Z[102]-Z[104]*Z[113])*Z[41];
  M[12][8] = -(Z[56]*Z[102]-Z[53]*Z[132])*Z[64];
  M[12][9] = -Z[67]*Z[49]*Z[102];
}

void V2_3__G__db__d__db__db__O3_0::Calculate_M13()
{
  M[13][1] = Z[137]*Z[27];
  M[13][2] = -(Z[80]*Z[102]-Z[117]*Z[101])*Z[34];
  M[13][3] = Z[41]*Z[83]*Z[102];
  M[13][8] = -Z[64]*Z[89]*Z[102];
  M[13][9] = -Z[67]*Z[84]*Z[134];
}

