from inspect import signature

from .. import atdecc_api as at
from ..aem.descriptors import *


class AEM:
    pass


class AEMCommand:
    pass


class AEMDescriptorFactory:
    registry = {}

    @staticmethod
    def register(descriptor_type, descriptor_class):
        AEMDescriptorFactory.registry[descriptor_type] = descriptor_class

    @staticmethod
    def create_descriptor(descriptor_type, descriptor_index, entity_info, config):
        descriptor_class = AEMDescriptorFactory.registry.get(descriptor_type)

        if not descriptor_class:
            raise ValueError(f"No descriptor class registered for type {descriptor_type}")

        descriptor_config = {}

        try:
            descriptor_config = config[descriptor_class.__name__]
        except KeyError:
            pass

        kwargs = {**vars(entity_info), **descriptor_config}
        init_sig = signature(descriptor_class.__init__)
        base_init_sig = None

        # check if the immediate parent class isn't object
        if descriptor_class.__bases__ != (object,):
            base_init_sig = signature(descriptor_class.__base__.__init__)

        init_parameters = {**init_sig.parameters, **base_init_sig.parameters}

        # filter kwargs
        allowed_kwargs = {'descriptor_index': descriptor_index, **{k: v for k, v in kwargs.items() if k in init_parameters}}

        return descriptor_class(**allowed_kwargs)

# TODO can we iterate over all existing subclasses of AEMDescriptor?
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_ENTITY, AEMDescriptor_ENTITY)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_CONFIGURATION, AEMDescriptor_CONFIGURATION)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT, AEMDescriptor_AUDIO_UNIT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT, AEMDescriptor_STREAM_INPUT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT, AEMDescriptor_STREAM_OUTPUT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_JACK_INPUT, AEMDescriptor_JACK_INPUT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_JACK_OUTPUT, AEMDescriptor_JACK_OUTPUT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE, AEMDescriptor_AVB_INTERFACE)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE, AEMDescriptor_CLOCK_SOURCE)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_INPUT, AEMDescriptor_STREAM_PORT_INPUT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_OUTPUT, AEMDescriptor_STREAM_PORT_OUTPUT)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_AUDIO_CLUSTER, AEMDescriptor_AUDIO_CLUSTER)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_AUDIO_MAP, AEMDescriptor_AUDIO_MAP)
AEMDescriptorFactory.register(at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN, AEMDescriptor_CLOCK_DOMAIN)
