#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

void V2_2__d__db__em__ep__O0_2__E1::SetCouplFlav(vector<Complex>& coupl)
{
  f[0] = 22;
  f[1] = 23;

  for (int i=0;i<6;i++) c[i] = coupl[i];
  for (int i=0;i<16;i++)
    for (int j=0;j<2;j++) M[i][j] = Complex(0.,0.);

  Z[0] = Complex(0.,0.);
}

void V2_2__d__db__em__ep__O0_2__E1::Calculate()
{
  for(int i=0;i<16;i++) cl[i] = 0;

  Z[1] = ZT<-1,-1,-1,-1>(1,0,2,3,c[0],c[0],c[1],c[1]);
  Z[2] = Pcalc(f[0],4);
  Z[5] = ZT<-1,-1,-1,-1>(1,0,2,3,c[2],c[3],c[4],c[5]);
  Z[6] = Pcalc(f[1],4);
  Z[7] = ZT<1,1,-1,-1>(1,0,2,3,c[0],c[0],c[1],c[1]);
  Z[9] = ZT<1,1,-1,-1>(1,0,2,3,c[2],c[3],c[4],c[5]);
  Z[10] = ZT<-1,-1,1,1>(1,0,2,3,c[0],c[0],c[1],c[1]);
  Z[11] = ZT<-1,-1,1,1>(1,0,2,3,c[2],c[3],c[4],c[5]);
  Z[12] = ZT<1,1,1,1>(1,0,2,3,c[0],c[0],c[1],c[1]);
  Z[13] = ZT<1,1,1,1>(1,0,2,3,c[2],c[3],c[4],c[5]);
}
