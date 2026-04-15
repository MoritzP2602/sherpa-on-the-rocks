#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__db__db__G__db__db__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__db__db__G__db__db__O3_0(bs);
}

V2_3__db__db__G__db__db__O3_0::V2_3__db__db__G__db__db__O3_0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Xfunc(0,_BS),
     Basic_Vfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[2];
  c = new Complex[4];
  Z = new Complex[208];
  M = new Complex*[32];
  for(int i=0;i<32;i++) M[i] = new Complex[10];
  cl = new int[32];
}

V2_3__db__db__G__db__db__O3_0::~V2_3__db__db__G__db__db__O3_0()
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

Complex V2_3__db__db__G__db__db__O3_0::Evaluate(int m,int n)
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

void V2_3__db__db__G__db__db__O3_0::Calculate_M0()
{
  M[0][0] = -Z[11]*Z[14];
  M[0][1] = (Z[7]*Z[15]+Z[18]*Z[17])*Z[21];
  M[0][2] = Z[28]*Z[22]*Z[7];
  M[0][3] = Z[33]*Z[7]*Z[31];
  M[0][4] = (Z[7]*Z[34]+Z[36]*Z[35])*Z[38];
  M[0][5] = Z[48]*Z[51];
  M[0][6] = -(Z[44]*Z[34]+Z[53]*Z[35])*Z[55];
  M[0][7] = -Z[58]*Z[22]*Z[44];
  M[0][8] = -Z[60]*Z[44]*Z[31];
  M[0][9] = -(Z[44]*Z[15]+Z[61]*Z[17])*Z[62];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M1()
{
  M[1][0] = -Z[66]*Z[14];
  M[1][1] = (Z[23]*Z[15]+Z[68]*Z[17])*Z[21];
  M[1][2] = Z[28]*Z[22]*Z[23];
  M[1][3] = Z[33]*Z[23]*Z[31];
  M[1][4] = (Z[23]*Z[34]+Z[73]*Z[35])*Z[38];
  M[1][5] = Z[77]*Z[51];
  M[1][6] = -(Z[56]*Z[34]+Z[79]*Z[35])*Z[55];
  M[1][7] = -Z[58]*Z[22]*Z[56];
  M[1][8] = -Z[60]*Z[56]*Z[31];
  M[1][9] = -(Z[56]*Z[15]+Z[82]*Z[17])*Z[62];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M2()
{
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M3()
{
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M4()
{
  M[4][0] = -Z[96]*Z[14];
  M[4][1] = Z[21]*Z[7]*Z[97];
  M[4][2] = -(Z[100]*Z[24]-Z[99]*Z[7])*Z[28];
  M[4][3] = -(Z[30]*Z[102]-Z[7]*Z[103])*Z[33];
  M[4][4] = Z[38]*Z[7]*Z[104];
  M[4][5] = Z[110]*Z[51];
  M[4][6] = -Z[55]*Z[44]*Z[104];
  M[4][7] = (Z[100]*Z[57]-Z[99]*Z[44])*Z[58];
  M[4][8] = (Z[59]*Z[102]-Z[44]*Z[103])*Z[60];
  M[4][9] = -Z[62]*Z[44]*Z[97];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M5()
{
  M[5][0] = -Z[112]*Z[14];
  M[5][1] = Z[21]*Z[23]*Z[97];
  M[5][2] = -(Z[113]*Z[24]-Z[99]*Z[23])*Z[28];
  M[5][3] = -(Z[72]*Z[102]-Z[23]*Z[103])*Z[33];
  M[5][4] = Z[38]*Z[23]*Z[104];
  M[5][5] = Z[116]*Z[51];
  M[5][6] = -Z[55]*Z[56]*Z[104];
  M[5][7] = (Z[113]*Z[57]-Z[99]*Z[56])*Z[58];
  M[5][8] = (Z[81]*Z[102]-Z[56]*Z[103])*Z[60];
  M[5][9] = -Z[62]*Z[56]*Z[97];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M6()
{
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M7()
{
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M8()
{
  M[8][0] = -Z[121]*Z[14];
  M[8][1] = Z[21]*Z[16]*Z[15];
  M[8][2] = -(Z[26]*Z[123]-Z[22]*Z[16])*Z[28];
  M[8][3] = Z[33]*Z[16]*Z[31];
  M[8][4] = (Z[16]*Z[34]+Z[125]*Z[35])*Z[38];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M9()
{
  M[9][0] = -Z[130]*Z[14];
  M[9][1] = Z[21]*Z[67]*Z[15];
  M[9][2] = -(Z[71]*Z[123]-Z[22]*Z[67])*Z[28];
  M[9][3] = Z[33]*Z[67]*Z[31];
  M[9][4] = (Z[67]*Z[34]+Z[132]*Z[35])*Z[38];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M10()
{
  M[10][5] = Z[139]*Z[51];
  M[10][6] = -(Z[86]*Z[34]+Z[141]*Z[35])*Z[55];
  M[10][7] = -Z[58]*Z[22]*Z[86];
  M[10][8] = (Z[126]*Z[83]-Z[86]*Z[31])*Z[60];
  M[10][9] = -Z[62]*Z[86]*Z[15];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M11()
{
  M[11][5] = Z[146]*Z[51];
  M[11][6] = -(Z[90]*Z[34]+Z[148]*Z[35])*Z[55];
  M[11][7] = -Z[58]*Z[22]*Z[90];
  M[11][8] = (Z[133]*Z[83]-Z[90]*Z[31])*Z[60];
  M[11][9] = -Z[62]*Z[90]*Z[15];
}

void V2_3__db__db__G__db__db__O3_0::Calculate_M12()
{
  M[12][0] = -Z[151]*Z[14];
  M[12][1] = (Z[16]*Z[97]+Z[19]*Z[152])*Z[21];
  M[12][2] = Z[28]*Z[99]*Z[16];
  M[12][3] = -(Z[124]*Z[102]-Z[16]*Z[103])*Z[33];
  M[12][4] = Z[38]*Z[16]*Z[104];
}

