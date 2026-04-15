// Channel_Generator3V
#include "PHASIC++/Channels/Single_Channel.H"
#include "ATOOLS/Org/Run_Parameter.H"
#include "ATOOLS/Org/MyStrStream.H"
#include "ATOOLS/Org/Scoped_Settings.H"
#include "PHASIC++/Channels/Channel_Elements.H"
#include "PHASIC++/Channels/Vegas.H"

using namespace PHASIC;
using namespace ATOOLS;

namespace PHASIC {
  class C3_9 : public Single_Channel {
    double m_thexp;
    double m_alpha,m_ctmax,m_ctmin;
    Info_Key m_kTC_0_3_1__2_4,m_kTC_0__1__3_24,m_kZS_0;
    Vegas* p_vegas;
  public:
    C3_9(int,int,Flavour*,Integration_Info * const);
    ~C3_9();
    void   GenerateWeight(Vec4D *,Cut_Data *);
    void   GeneratePoint(Vec4D *,Cut_Data *,double *);
    void   AddPoint(double);
    void   MPISync()                 { p_vegas->MPISync(); }
    void   Optimize()                { p_vegas->Optimize(); } 
    void   EndOptimize()             { p_vegas->EndOptimize(); } 
    void   WriteOut(std::string pId) { p_vegas->WriteOut(pId); } 
    void   ReadIn(std::string pId)   { p_vegas->ReadIn(pId); } 
    void   ISRInfo(int &,double &,double &);
    std::string ChID();
  };
}

extern "C" Single_Channel * Getter_C3_9(int nin,int nout,Flavour* fl,Integration_Info * const info) {
  return new C3_9(nin,nout,fl,info);
}

void C3_9::GeneratePoint(Vec4D * p,Cut_Data * cuts,double * _ran)
{
  double *ran = p_vegas->GeneratePoint(_ran);
  for(size_t i=0;i<m_rannum;i++) p_rans[i]=ran[i];
  Vec4D p234=p[0]+p[1];
  double s234_max = p234.Abs2();
  double s24_max = sqr(sqrt(s234_max)-sqrt(p_ms[3]));
  double s4 = p_ms[4];
  double s2 = p_ms[2];
  double s24_min = cuts->GetscutAmegic(std::string("24"));
  Vec4D  p24;
  double s24 = CE.ThresholdMomenta(m_thexp,4.*sqrt(s24_min),s24_min,s24_max,ran[0]);
  double s3 = p_ms[3];
  CE.TChannelMomenta(p[0],p[1],p[3],p24,s3,s24,0.,m_alpha,m_ctmax,m_ctmin,ran[1],ran[2]);
  Vec4D  p0_3 = p[0]-p[3];
  CE.TChannelMomenta(p0_3,p[1],p[2],p[4],s2,s4,0.,m_alpha,m_ctmax,m_ctmin,ran[3],ran[4]);
}

void C3_9::GenerateWeight(Vec4D* p,Cut_Data * cuts)
{
  double wt = 1.;
  Vec4D p234=p[0]+p[1];
  double s234_max = p234.Abs2();
  double s24_max = sqr(sqrt(s234_max)-sqrt(p_ms[3]));
  double s4 = p_ms[4];
  double s2 = p_ms[2];
  double s24_min = cuts->GetscutAmegic(std::string("24"));
  Vec4D  p24 = p[2]+p[4];
  double s24 = dabs(p24.Abs2());
  wt *= CE.ThresholdWeight(m_thexp,4.*sqrt(s24_min),s24_min,s24_max,s24,p_rans[0]);
  double s3 = p_ms[3];
  if (m_kTC_0__1__3_24.Weight()==ATOOLS::UNDEFINED_WEIGHT)
    m_kTC_0__1__3_24<<CE.TChannelWeight(p[0],p[1],p[3],p24,0.,m_alpha,m_ctmax,m_ctmin,m_kTC_0__1__3_24[0],m_kTC_0__1__3_24[1]);
  wt *= m_kTC_0__1__3_24.Weight();

  p_rans[1]= m_kTC_0__1__3_24[0];
  p_rans[2]= m_kTC_0__1__3_24[1];
  Vec4D  p0_3 = p[0]-p[3];
  if (m_kTC_0_3_1__2_4.Weight()==ATOOLS::UNDEFINED_WEIGHT)
    m_kTC_0_3_1__2_4<<CE.TChannelWeight(p0_3,p[1],p[2],p[4],0.,m_alpha,m_ctmax,m_ctmin,m_kTC_0_3_1__2_4[0],m_kTC_0_3_1__2_4[1]);
  wt *= m_kTC_0_3_1__2_4.Weight();

  p_rans[3]= m_kTC_0_3_1__2_4[0];
  p_rans[4]= m_kTC_0_3_1__2_4[1];
  double vw = p_vegas->GenerateWeight(p_rans);
  if (wt!=0.) wt = vw/wt/pow(2.*M_PI,3*3.-4.);

  m_weight = wt;
}

C3_9::C3_9(int nin,int nout,Flavour* fl,Integration_Info * const info)
       : Single_Channel(nin,nout,fl)
{
  Settings& s = Settings::GetMainSettings();
  m_name = std::string("C3_9");
  m_rannum = 5;
  p_rans  = new double[m_rannum];
  m_thexp = s["THRESHOLD_EXPONENT"].Get<double>();
  m_alpha = s["TCHANNEL_ALPHA"].Get<double>();
  m_ctmax = 1.;
  m_ctmin = -1.;
  m_kTC_0_3_1__2_4.Assign(std::string("TC_0_3_1__2_4"),2,0,info);
  m_kTC_0__1__3_24.Assign(std::string("TC_0__1__3_24"),2,0,info);
  m_kZS_0.Assign(std::string("ZS_0"),2,0,info);
  p_vegas = new Vegas(m_rannum,100,m_name);
}

C3_9::~C3_9()
{
  delete p_vegas;
}

void C3_9::ISRInfo(int & type,double & mass,double & width)
{
  type  = 2;
  mass  = 0;
  width = 0.;
}

void C3_9::AddPoint(double Value)
{
  Single_Channel::AddPoint(Value);
  p_vegas->AddPoint(Value,p_rans);
}
std::string C3_9::ChID()
{
  return std::string("CG2$MTH_24$TC_0_3_1__2_4$TC_0__1__3_24$ZS_0$");
}
