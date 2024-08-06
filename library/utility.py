from aws_cdk import (
    aws_ec2 as ec2
)

class Utility():

    def __init__(self):
        pass
        
    def getSubnetSelection(self, vpc: ec2.Vpc, subnet_ids: list = None, availability_zones: list = None):
        # Inspired from https://python.plainenglish.io/importing-existing-vpc-and-subnets-into-a-cdk-python-project-a707d61de4c3
        
        subnets_in_az = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, 
                                                 availability_zones=availability_zones)        
        
        az_lookup = {}
        for subnet in subnets_in_az.subnets:
            if subnet_ids is not None:
                # add only subnets specified by user
                for selected_subnet in subnet_ids:
                    if selected_subnet == subnet.subnet_id:
                        az_lookup[subnet.subnet_id] = subnet.availability_zone
            else:
                az_lookup[subnet.subnet_id] = subnet.availability_zone

        subnets = []
        for id, az in az_lookup.items():
            subnets.append(ec2.Subnet.from_subnet_attributes(self, "Subnet"+id+az, subnet_id=id, availability_zone=az))

        return ec2.SubnetSelection(subnets=subnets)