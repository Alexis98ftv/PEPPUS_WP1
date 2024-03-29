#!/usr/bin/env python

########################################################################
# PETRUS/SRC/Preprocessing.py:
# This is the Preprocessing Module of PEPPUS tool
#
#  Project:        PEPPUS
#  File:           Preprocessing.py
#  Date(YY/MM/DD): 01/02/21
#
#   Author: GNSS Academy
#   Copyright 2021 GNSS Academy
#
# -----------------------------------------------------------------
# Date       | Author             | Action
# -----------------------------------------------------------------
#
########################################################################


# Import External and Internal functions and Libraries
#----------------------------------------------------------------------
import sys, os

# Add path to find all modules
Common = os.path.dirname(os.path.dirname(
    os.path.abspath(sys.argv[0]))) + '/COMMON'
sys.path.insert(0, Common)
from collections import OrderedDict
from COMMON import GnssConstants as Const
from InputOutput import RcvrIdx, ObsIdx, REJECTION_CAUSE
from InputOutput import FLAG, VALUE, TH, CSNEPOCHS, CSNPOINTS, CSPDEGREE
import numpy as np
from COMMON.Iono import computeIonoMappingFunction

# Preprocessing internal functions
#-----------------------------------------------------------------------


def runPreProcMeas(Conf, Rcvr, ObsInfo, PrevPreproObsInfo):
    
    # Purpose: preprocess GNSS raw measurements from OBS file
    #          and generate PREPRO OBS file with the cleaned,
    #          smoothed measurements

    #          More in detail, this function handles:

    #          * Measurements cleaning and validation and exclusion due to different 
    #          criteria as follows:
    #             - Minimum Masking angle
    #             - Maximum Number of channels
    #             - Minimum Carrier-To-Noise Ratio (CN0)
    #             - Pseudo-Range Output of Range 
    #             - Maximum Pseudo-Range Step
    #             - Maximum Pseudo-Range Rate
    #             - Maximum Carrier Phase Increase
    #             - Maximum Carrier Phase Increase Rate
    #             - Data Gaps checks and handling 
    #             - Cycle Slips detection

    #          * Build iono-free combination

    # Parameters
    # ==========
    # Conf: dict
    #         Configuration dictionary
    # Rcvr: list
    #         Receiver information: position, masking angle...
    # ObsInfo: list
    #         OBS info for current epoch
    #         ObsInfo[1][1] is the second field of the 
    #         second satellite
    # PrevPreproObsInfo: dict
    #         Preprocessed observations for previous epoch per sat
    #         PrevPreproObsInfo["G01"]["C1"]

    # Returns
    # =======
    # PreproObsInfo: dict
    #         Preprocessed observations for current epoch per sat
    #         PreproObsInfo["G01"]["C1"]

    # Initialize output
    PreproObsInfo = OrderedDict({})
    
    # Limit the satellites to the Number of Channels
    # If the number of satellites in view exceeds the maximum allowed channels
    # ----------------------------------------------------------
    NSATS = len(ObsInfo)
    index_array = []
    if(NSATS > Conf["NCHANNELS_GPS"]):
        lowest_elev = 100.0
        lowest_index = 0
        while(NSATS != Conf["NCHANNELS_GPS"]):
            for index in range(0, len(ObsInfo) - 1):
                if(index not in index_array):
                    elev = float(ObsInfo[index][ObsIdx["ELEV"]])
                    if(elev < lowest_elev):
                        lowest_elev = elev
                        lowest_index = index
            index_array.append(lowest_index)
            lowest_elev = 100.0
            NSATS = NSATS - 1
    
    # Loop over satellites
    for SatObs in ObsInfo:
        # Initialize output info
        SatPreproObsInfo = {
            "Sod": 0.0,                         # Second of day
            "Doy": 0,                           # Day of year
            "Elevation": 0.0,                   # Elevation
            "Azimuth": 0.0,                     # Azimuth
            "C1": 0.0,                          # GPS L1C/A pseudorange
            "L1": 0.0,                          # GPS L1 carrier phase (in cycles)
            "L1Meters": 0.0,                    # GPS L1 carrier phase (in m)
            "S1": 0.0,                          # GPS L1C/A C/No
            "P2": 0.0,                          # GPS L2P pseudorange
            "L2": 0.0,                          # GPS L2 carrier phase (in cycles)
            "L2Meters": 0.0,                    # GPS L2 carrier phase (in m)
            "S2": 0.0,                          # GPS L2 C/No
            "IF_C": 0.0,                        # Iono-Free combination of codes
            "IF_L": 0.0,                        # Iono-Free combination of phases
            "Status": 1,                        # Measurement status
            "RejectionCause": 0,                # Cause of rejection flag
            "CodeRate": Const.NAN,              # Code Rate
            "CodeRateStep": Const.NAN,          # Code Rate Step
            "PhaseRate": Const.NAN,             # Phase Rate
            "PhaseRateStep": Const.NAN,         # Phase Rate Step
            "GF_L": Const.NAN,                  # Geometry-Free combination of phases in meters
            "VtecRate": Const.NAN,              # VTEC Rate
            "iAATR": Const.NAN,                 # Instantaneous AATR 
            "Mpp": 0.0,                         # Iono Mapping
            
        } # End of SatPreproObsInfo

        # Get satellite label
        SatLabel = SatObs[ObsIdx["CONST"]] + "%02d" % int(SatObs[ObsIdx["PRN"]])

        # Prepare outputs
        # ----------------------------------------------------------
        # Get SoD
        SatPreproObsInfo["Sod"] = float(SatObs[ObsIdx["SOD"]])
        # Get DoY
        SatPreproObsInfo["Doy"] = int(SatObs[ObsIdx["DOY"]])
        # Get Elevation
        SatPreproObsInfo["Elevation"] = float(SatObs[ObsIdx["ELEV"]])
        # Get Azimuth
        SatPreproObsInfo["Azimuth"] = float(SatObs[ObsIdx["AZIM"]])
        # Get GPS L1C/A pseudorange
        SatPreproObsInfo["C1"] = float(SatObs[ObsIdx["C1"]])
        # Get GPS L1 carrier phase (in cycles)
        SatPreproObsInfo["L1"] = float(SatObs[ObsIdx["L1"]])
        # Get GPS L1 carrier phase (in m)
        SatPreproObsInfo["L1Meters"] = SatPreproObsInfo["L1"] * Const.GPS_L1_WAVE
        # Get GPS L1C/A C/No
        SatPreproObsInfo["S1"] = float(SatObs[ObsIdx["S1"]])
        # Get GPS L2P pseudorange
        SatPreproObsInfo["P2"] = float(SatObs[ObsIdx["P2"]])
        # Get GPS L2 carrier phase (in cycles)
        SatPreproObsInfo["L2"] = float(SatObs[ObsIdx["L2"]])
        # Get GPS L2 carrier phase (in m)
        SatPreproObsInfo["L2Meters"] = SatPreproObsInfo["L2"] * Const.GPS_L2_WAVE
        # Get GPS L2 C/No
        SatPreproObsInfo["S2"] = float(SatObs[ObsIdx["S2"]])     
        

        # Prepare output for the satellite
        PreproObsInfo[SatLabel] = SatPreproObsInfo

        # Limit the satellites to the Number of Channels
        # ----------------------------------------------------------
        if(len(index_array) != 0):
            for index in index_array:
                if(SatObs == ObsInfo[index]):
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["NCHANNELS_GPS"]

        # Check measurement data gaps
        #-------------------------------------------------------------------------------
        DeltaT = SatPreproObsInfo["Sod"] - PrevPreproObsInfo[SatLabel]["PrevEpoch"]
        if (DeltaT > Conf["MAX_GAP"][1]): 
                # Check if gap detection is activated and do not tag non-visibility periods as data gaps
                if (Conf["MAX_GAP"][0] and PrevPreproObsInfo[SatLabel]["PrevRej"] != REJECTION_CAUSE["MASKANGLE"]):  
                    # Flag the measurement as a data gap
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["DATA_GAP"]

                # Reset previous info
                PrevPreproObsInfo[SatLabel]["CycleSlipBuffIdx"] = 0
                PrevPreproObsInfo[SatLabel]["CycleSlipFlagIdx"] = 0
                PrevPreproObsInfo[SatLabel]["GF_L_Prev"] = [0.0] * int(Conf["CYCLE_SLIPS"][CSNPOINTS])
                PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"] = [0.0] * int(Conf["CYCLE_SLIPS"][CSNPOINTS])
                PrevPreproObsInfo[SatLabel]["CycleSlipFlags"] = [0.0] * int(Conf["CYCLE_SLIPS"][CSNEPOCHS])

                PrevPreproObsInfo[SatLabel]["PrevCode"] = Const.NAN
                PrevPreproObsInfo[SatLabel]["PrevPhase"] = Const.NAN
                PrevPreproObsInfo[SatLabel]["PrevCodeRate"] = Const.NAN
                PrevPreproObsInfo[SatLabel]["PrevPhaseRate"] = Const.NAN
                PrevPreproObsInfo[SatLabel]["PrevStec"] = Const.NAN
                PrevPreproObsInfo[SatLabel]["PrevStecEpoch"] = Const.NAN

        # Build measurement combinations
        #-------------------------------------------------------------------------------
        # Check that both Measurements exist at the same time
        if(SatPreproObsInfo["C1"]>0.0 and SatPreproObsInfo["P2"]>0.0):
            # Build Iono-free combination of codes and phases
            #---------------------------------------------------------------------------
            SatPreproObsInfo["IF_C"] = (SatPreproObsInfo["P2"]-Const.GPS_GAMMA_L1L2*SatPreproObsInfo["C1"])/ \
                (1-Const.GPS_GAMMA_L1L2)
            SatPreproObsInfo["IF_L"] = (SatPreproObsInfo["L2Meters"]-Const.GPS_GAMMA_L1L2*SatPreproObsInfo["L1Meters"])/ \
                (1-Const.GPS_GAMMA_L1L2)

            # Build Geometry-free combination of phases
            #---------------------------------------------------------------------------
            #Pgeomfree=(SatPreproObsInfo["C1"]-SatPreproObsInfo["P2"])/(1-Const.GPS_GAMMA_L1L2)
            #Lgeomfree=(SatPreproObsInfo["L1Meters"]-SatPreproObsInfo["L2Meters"])/(Const.GPS_GAMMA_L1L2-1)

            SatPreproObsInfo["GF_L"] = SatPreproObsInfo["L1Meters"] - SatPreproObsInfo["L2Meters"]
            GF_L_cycles = SatPreproObsInfo["L1"] - SatPreproObsInfo["L2"]

        # Check satellite Elevation angle in front of the minimum by configuration
        # ----------------------------------------------------------
        if(SatPreproObsInfo["Elevation"] < Rcvr[RcvrIdx["MASK"]]):
            SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MASKANGLE"]

        # Measurement quality monitoring
        #-------------------------------------------------------------------------------
        # Check Signal To Noise Ratio in front of Minimum by configuration (if activated)
        #-------------------------------------------------------------------------------
        if(Conf["MIN_SNR"][0] == 1):
            if(SatPreproObsInfo["S1"] < Conf["MIN_SNR"][1]):
                SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MIN_SNR_L1"]
            if(SatPreproObsInfo["S2"] < Conf["MIN_SNR"][1]):
                SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MIN_SNR_L2"]

        # Check Pseudo-ranges Out-of-Range in front of Maximum by configuration
        #-------------------------------------------------------------------------------
        if(Conf["MAX_PSR_OUTRNG"][0] == 1):
            if(SatPreproObsInfo["C1"] > Conf["MAX_PSR_OUTRNG"][1]):
                SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MAX_PSR_OUTRNG_L1"]
            if(SatPreproObsInfo["P2"] > Conf["MAX_PSR_OUTRNG"][1]):
                SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MAX_PSR_OUTRNG_L2"]

        #-------------------------------------------------------------------------------
        #[CHALLENGE] # Check Cycle Slips, if activated
        #-------------------------------------------------------------------------------
        # fit a polynomial using previous GF measurements to compare the predicted value 
        # with the observed one
        #-------------------------------------------------------------------------------
        if(Conf["CYCLE_SLIPS"][0] == 1): 
            # If the buffer is full, we can detect the cycle slip with a polynom
            if (PrevPreproObsInfo[SatLabel]["CycleSlipBuffIdx"] == Conf["CYCLE_SLIPS"][3]): # number of points (7)
                # Adjust polynom to the samples in the buffer
                Polynom = np.polynomial.polynomial.polyfit(
                    PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"],
                    PrevPreproObsInfo[SatLabel]["GF_L_Prev"],
                    int(Conf["CYCLE_SLIPS"][4])) # degree of polynom (2) Conf["CYCLE_SLIPS"][4] TypeError: deg must be an int or non-empty 1-D array of int
                
                # Predict Target value evaluating the polynom
                Targetpred = np.polynomial.polynomial.polyval(SatPreproObsInfo["Sod"], Polynom)

                # Compute Residual
                Residual = abs(GF_L_cycles - Targetpred)

                # Compute CS flag --> Check Residual against Threshold
                if(Residual > Conf["CYCLE_SLIPS"][1]): # Threshold (0.5)
                    CSflag = 1
                else:
                    CSflag = 0
                
                # Update CS flag buffer
                if CSflag == 1:
                    PrevPreproObsInfo[SatLabel]["CycleSlipFlags"][PrevPreproObsInfo[SatLabel]["CycleSlipFlagIdx"]] = CSflag
                    PrevPreproObsInfo[SatLabel]["CycleSlipFlagIdx"] += 1
                    # Set the measurement as Not Valid 
                    SatPreproObsInfo["Status"] = 0
                else:
                    PrevPreproObsInfo[SatLabel]["CycleSlipFlags"][PrevPreproObsInfo[SatLabel]["CycleSlipFlagIdx"]] = CSflag
                    
                # Check if threshold was exceeded CSNEPOCHS times
                if (sum(PrevPreproObsInfo[SatLabel]["CycleSlipFlags"]) == Conf["CYCLE_SLIPS"][2]):
                    #print("cycleslip", SatPreproObsInfo["Sod"] / Const.S_IN_H) ##DEBUGGING
                    # Set measurement as Not Valid
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["CYCLE_SLIP"]
                    
                    # Reset previous info
                    PrevPreproObsInfo[SatLabel]["CycleSlipBuffIdx"] = 0
                    PrevPreproObsInfo[SatLabel]["CycleSlipFlagIdx"] = 0
                    PrevPreproObsInfo[SatLabel]["GF_L_Prev"] = [0.0] * int(Conf["CYCLE_SLIPS"][CSNPOINTS])
                    PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"] = [0.0] * int(Conf["CYCLE_SLIPS"][CSNPOINTS])
                    PrevPreproObsInfo[SatLabel]["CycleSlipFlags"] = [0.0] * int(Conf["CYCLE_SLIPS"][CSNEPOCHS])

                    PrevPreproObsInfo[SatLabel]["PrevCode"] = Const.NAN
                    PrevPreproObsInfo[SatLabel]["PrevPhase"] = Const.NAN
                    PrevPreproObsInfo[SatLabel]["PrevCodeRate"] = Const.NAN
                    PrevPreproObsInfo[SatLabel]["PrevPhaseRate"] = Const.NAN
                    PrevPreproObsInfo[SatLabel]["PrevStec"] = Const.NAN
                    PrevPreproObsInfo[SatLabel]["PrevStecEpoch"] = Const.NAN
                    # Set the measurement as Not Valid 
                    SatPreproObsInfo["Status"] = 0
                else:

                    # Update the buffer
                    if CSflag != 1:
                        # Leave space for the new sample
                        PrevPreproObsInfo[SatLabel]["GF_L_Prev"][:-1] = PrevPreproObsInfo[SatLabel]["GF_L_Prev"][1:]
                        PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"][:-1] = PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"][1:]

                        # Store new sample
                        PrevPreproObsInfo[SatLabel]["GF_L_Prev"][-1] = GF_L_cycles
                        PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"][-1] = SatPreproObsInfo["Sod"]
            
            # If the buffer is not full, fill the buffer
            else:
                # Fill the buffer 
                PrevPreproObsInfo[SatLabel]["GF_L_Prev"][PrevPreproObsInfo[SatLabel]["CycleSlipBuffIdx"]] = GF_L_cycles
                PrevPreproObsInfo[SatLabel]["GF_Epoch_Prev"][PrevPreproObsInfo[SatLabel]["CycleSlipBuffIdx"]] = SatPreproObsInfo["Sod"]
                # Increase Idx Buffer
                PrevPreproObsInfo[SatLabel]["CycleSlipBuffIdx"] += 1
                # Set the measurement as Not Valid 
                SatPreproObsInfo["Status"] = 0
        

        # Check Phase Rate (if activated) # MAX_PHASE_RATE 952.0
        #-------------------------------------------------------------------------------
        # Compute the Phase Rate in m/s
        if(PrevPreproObsInfo[SatLabel]["PrevPhase"] != Const.NAN):
            SatPreproObsInfo["PhaseRate"] = (SatPreproObsInfo["L1Meters"] - PrevPreproObsInfo[SatLabel]["PrevPhase"]) / DeltaT
            if(Conf["MAX_PHASE_RATE"][0] == 1):
                # Check Phase Jump
                if(abs(SatPreproObsInfo["PhaseRate"] > Conf["MAX_PHASE_RATE"][1])):
                    # Reject the measurement setting flag: Max Phase Rate
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MAX_PHASE_RATE"]
        else:
            SatPreproObsInfo["Status"] = 0
           
        # Check Phase Rate Step (if activated)
        #-------------------------------------------------------------------------------
        # Compute the Phase Rate Step in m/s2
        if(PrevPreproObsInfo[SatLabel]["PrevPhaseRate"] != Const.NAN):
            SatPreproObsInfo["PhaseRateStep"] = (SatPreproObsInfo["PhaseRate"] - PrevPreproObsInfo[SatLabel]["PrevPhaseRate"]) / DeltaT
            if(Conf["MAX_PHASE_RATE_STEP"][0] == 1):
                # Check Phase Rate Jump
                if(abs(SatPreproObsInfo["PhaseRateStep"] > Conf["MAX_PHASE_RATE_STEP"][1])):
                    # Reject the measurement setting flag: Max Phase Rate Step
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MAX_PHASE_RATE_STEP"]
        else:
            SatPreproObsInfo["Status"] = 0

        # Check Code Rate detector (if activated)
        #-------------------------------------------------------------------------------
        # Compute the Code Rate in m/s as the first derivative of Raw Codes
        if(PrevPreproObsInfo[SatLabel]["PrevCode"] != Const.NAN):
            SatPreproObsInfo["CodeRate"] = (SatPreproObsInfo["C1"] - PrevPreproObsInfo[SatLabel]["PrevCode"]) / DeltaT
            if(Conf["MAX_CODE_RATE"][0] == 1):
                # Check Code Jump
                if(abs(SatPreproObsInfo["CodeRate"] > Conf["MAX_CODE_RATE"][1])):
                    # Reject the measurement setting flag: Max Code Rate
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MAX_CODE_RATE"]
        else:
            SatPreproObsInfo["Status"] = 0

        # Check Code Rate Step detector (if activated)
        #-------------------------------------------------------------------------------
        # Compute the Code Rate step in m/s2 as the second derivative of Raw Codes
        if(PrevPreproObsInfo[SatLabel]["PrevCodeRate"] != Const.NAN):
            SatPreproObsInfo["CodeRateStep"] = (SatPreproObsInfo["CodeRate"] - PrevPreproObsInfo[SatLabel]["PrevCodeRate"]) / DeltaT
            if(Conf["MAX_CODE_RATE_STEP"][0] == 1):
                # Check Code Rate Jump
                if(abs(SatPreproObsInfo["CodeRateStep"]) > Conf["MAX_CODE_RATE_STEP"][1]):
                    # Reject the measurement setting flag: Max Code Rate Step
                    SatPreproObsInfo["RejectionCause"] = REJECTION_CAUSE["MAX_CODE_RATE_STEP"]
        else:
            SatPreproObsInfo["Status"] = 0

        #-------------------------------------------------------------------------------
        # Set Status to 0 (invalid measurement) in case of rejection cause flag
        #-------------------------------------------------------------------------------
        if(SatPreproObsInfo["RejectionCause"] != REJECTION_CAUSE["NO_REJECTION"]):
            SatPreproObsInfo["Status"] = 0
        
        #-------------------------------------------------------------------------------
        # Compute Iono Mapping Function as per MOPS Standard
        #-------------------------------------------------------------------------------
        # Compute Iono Mapping Function as per MOPS Standard
        SatPreproObsInfo["Mpp"] = computeIonoMappingFunction(SatPreproObsInfo["Elevation"])

        # Check if previous observable is valid
        #-------------------------------------------------------------------------------
        if (PrevPreproObsInfo[SatLabel]["PrevStec"] != Const.NAN and SatPreproObsInfo["Status"] == 1):
            DeltaTstec = SatPreproObsInfo["Sod"] - PrevPreproObsInfo[SatLabel]["PrevStecEpoch"]
            # Estimate STEC Gradient
            DeltaSTEC = (((SatPreproObsInfo["GF_L"] - PrevPreproObsInfo[SatLabel]["PrevStec"]) / (1-Const.GPS_GAMMA_L1L2)) / DeltaTstec) * Const.M_IN_MM

            # Estimate VTEC Gradient - VTECRate = DeltaVTEC
            SatPreproObsInfo["VtecRate"] = DeltaSTEC / SatPreproObsInfo["Mpp"] 

            # Compute instantaneous AATR
            SatPreproObsInfo["iAATR"] = SatPreproObsInfo["VtecRate"] / SatPreproObsInfo["Mpp"]

            #---------------------------------------------------------
            # Winmerge ==> detect diff between (0.000) and (-0.000)
            #---------------------------------------------------------
            if SatPreproObsInfo["VtecRate"] == -0.000:
                SatPreproObsInfo["VtecRate"] = 0.000
            if SatPreproObsInfo["iAATR"] == -0.000:
                SatPreproObsInfo["iAATR"] = 0.000
            #---------------------------------------------------------
            
        #-------------------------------------------------------------------------------
        # Store current values into previous ones for next iteration
        #-------------------------------------------------------------------------------
        PrevPreproObsInfo[SatLabel]["PrevEpoch"] = SatPreproObsInfo["Sod"]
        PrevPreproObsInfo[SatLabel]["PrevL1"] = SatPreproObsInfo["L1"]
        PrevPreproObsInfo[SatLabel]["PrevL2"] = SatPreproObsInfo["L2"]
        PrevPreproObsInfo[SatLabel]["PrevC1"] = SatPreproObsInfo["C1"]
        PrevPreproObsInfo[SatLabel]["PrevP2"] = SatPreproObsInfo["P2"]
        PrevPreproObsInfo[SatLabel]["PrevRej"] = SatPreproObsInfo["RejectionCause"]

        # Just for C1 and L1 (in meters) (to not duplicate code in python)
        PrevPreproObsInfo[SatLabel]["PrevCode"] = SatPreproObsInfo["C1"]
        PrevPreproObsInfo[SatLabel]["PrevPhase"] = SatPreproObsInfo["L1Meters"]
        # Derivatives
        PrevPreproObsInfo[SatLabel]["PrevCodeRate"] = SatPreproObsInfo["CodeRate"]
        PrevPreproObsInfo[SatLabel]["PrevPhaseRate"] = SatPreproObsInfo["PhaseRate"]
        # PrevStec
        if SatPreproObsInfo["Status"] != 0:
            PrevPreproObsInfo[SatLabel]["PrevStec"] = SatPreproObsInfo["GF_L"]
            PrevPreproObsInfo[SatLabel]["PrevStecEpoch"] = SatPreproObsInfo["Sod"]
            
            
    return PreproObsInfo

# End of function runPreProcMeas()

########################################################################
# END OF PREPROCESSING FUNCTIONS MODULE
########################################################################
